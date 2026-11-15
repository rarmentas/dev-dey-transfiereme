import 'dart:async';

import 'package:cody/features/pedidos/data/pedido.dart';
import 'package:cody/features/pedidos/data/pedido_repository.dart';
import 'package:cody/features/pedidos/presentation/pedido_detalle_page.dart';
import 'package:cody/features/pedidos/presentation/pedido_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../support/mock_pedido_api.dart';

class RepoAcciones extends PedidoRepository {
  RepoAcciones() : super(crearDioPedido());
  String pago = 'sin_cobro', preparacion = 'pendiente';
  String? pagoDespuesCobro;
  bool avanzarListo = true;
  PedidoException? errorCarga, errorAccion;
  int lecturas = 0;
  Completer<void>? demora;
  final List<Map<String, dynamic>> solicitudes = [];
  Pedido obtenerPedido() {
    final json = pedidoJson(aceptado: true);
    json['pago_estado'] = pago;
    json['preparacion'] = preparacion;
    json['intento'] = {
      'intento_id': 'i1',
      'qr': 'qr-prueba',
      'vencimiento': 'mañana',
    };
    json['entrega'] = {
      'listo_por': 'Ana',
      'listo_en': '2026-01-01',
      if (preparacion == 'entregado') 'entregado_por': 'Luis',
    };
    return Pedido.fromJson(json);
  }

  @override
  Future<Pedido> obtener(String id) async {
    lecturas++;
    if (errorCarga != null) throw errorCarga!;
    return obtenerPedido();
  }

  Future<Pedido> ejecutar(String accion, Map<String, dynamic> cuerpo) async {
    solicitudes.add({'ruta': accion, ...cuerpo});
    if (demora != null) await demora!.future;
    if (errorAccion != null) throw errorAccion!;
    if (accion == 'cobro' && pagoDespuesCobro != null) pago = pagoDespuesCobro!;
    if (accion == 'listo' && avanzarListo) preparacion = 'listo';
    if (accion == 'entregado') preparacion = 'entregado';
    return obtenerPedido();
  }

  @override
  Future<Pedido> cobro(String id, Map<String, dynamic> cuerpo) =>
      ejecutar('cobro', cuerpo);
  @override
  Future<Pedido> listo(String id, Map<String, dynamic> cuerpo) =>
      ejecutar('listo', cuerpo);
  @override
  Future<Pedido> entregado(String id, Map<String, dynamic> cuerpo) =>
      ejecutar('entregado', cuerpo);
}

Future<void> abrir(WidgetTester t, RepoAcciones repo) async {
  await t.pumpWidget(
    ProviderScope(
      overrides: [pedidoRepositoryProvider.overrideWithValue(repo)],
      child: const MaterialApp(home: PedidoDetallePage(id: 'abc')),
    ),
  );
  await t.pump();
  await t.pump();
}

Future<void> pulsar(WidgetTester t, String nombre) async {
  await t.ensureVisible(find.text(nombre));
  await t.tap(find.text(nombre));
  await t.pump();
  await t.pump(const Duration(milliseconds: 300));
  await t.drag(find.byType(ListView).first, const Offset(0, 600));
  await t.pump();
}

PedidoException error(String codigo, int? status) =>
    PedidoException(codigo, status, codigo);

void main() {
  for (final estado in ['en_espera', 'reservado', 'enviando', 'pendiente']) {
    testWidgets('polling $estado cada dos segundos y cancela al salir', (
      t,
    ) async {
      final repo = RepoAcciones()..pago = estado;
      await abrir(t, repo);
      expect(repo.lecturas, 1);
      await t.pump(const Duration(milliseconds: 1999));
      expect(repo.lecturas, 1);
      await t.pump(const Duration(milliseconds: 1));
      await t.pump();
      expect(repo.lecturas, 2);
      await t.pumpWidget(const SizedBox());
      await t.pump(const Duration(seconds: 3));
      expect(repo.lecturas, 2);
    });
  }
  for (final estado in [
    'sin_cobro',
    'incierto',
    'pagado',
    'rechazado',
    'descartado',
    'vencido',
  ]) {
    testWidgets('$estado no hace polling', (t) async {
      final repo = RepoAcciones()..pago = estado;
      await abrir(t, repo);
      await t.pump(const Duration(seconds: 5));
      expect(repo.lecturas, 1);
    });
  }
  for (final codigo in ['RED', 'SERVICIO_NO_DISPONIBLE']) {
    testWidgets('$codigo al refrescar conserva ultimo estado', (t) async {
      final repo = RepoAcciones()..pago = 'pendiente';
      await abrir(t, repo);
      repo.errorCarga = error(codigo, codigo == 'RED' ? null : 503);
      await t.pump(const Duration(seconds: 2));
      await t.pump();
      expect(repo.lecturas, 2);
      expect(find.text('Pago pendiente'), findsOneWidget);
      expect(find.text(codigo), findsOneWidget);
      await t.pumpWidget(const SizedBox());
    });
  }
  testWidgets('solicitar y activar usan claves independientes', (t) async {
    final repo = RepoAcciones()..pagoDespuesCobro = 'en_espera';
    await abrir(t, repo);
    await pulsar(t, 'Cobrar');
    final clave = repo.solicitudes.single['command_key'];
    await pulsar(t, 'Activar cobro');
    expect(repo.solicitudes.last['command_key'], isNot(clave));
  });
  testWidgets('listo exitoso limpia clave aun con mismo payload', (t) async {
    final repo = RepoAcciones()
      ..pago = 'pagado'
      ..avanzarListo = false;
    await abrir(t, repo);
    await pulsar(t, 'Marcar listo');
    await pulsar(t, 'Marcar listo');
    expect(
      repo.solicitudes.first['command_key'],
      isNot(repo.solicitudes.last['command_key']),
    );
  });

  testWidgets('detalle sin cobro ofrece QR y envia payload', (t) async {
    final repo = RepoAcciones();
    await abrir(t, repo);
    expect(find.text('Sin cobro'), findsOneWidget);
    expect(find.byType(QrImageView), findsNothing);
    expect(find.text('Solicitado: Leche'), findsOneWidget);
    expect(find.text('Preparación pendiente'), findsOneWidget);
    await pulsar(t, 'Cobrar');
    expect(repo.solicitudes.single, containsPair('accion', 'solicitar'));
    expect(repo.solicitudes.single, containsPair('canal', 'qr_venta'));
    expect(repo.solicitudes.single, containsPair('expected_version', 1));
    expect(repo.solicitudes.single['command_key'], isNotEmpty);
  });
  testWidgets('push exige telefono de diez digitos y lo envia confirmado', (
    t,
  ) async {
    final repo = RepoAcciones();
    await abrir(t, repo);
    await t.tap(find.byType(DropdownButton<String>).first);
    await t.pumpAndSettle();
    await t.tap(find.text('Enviar al celular').last);
    await t.pumpAndSettle();
    await pulsar(t, 'Cobrar');
    expect(repo.solicitudes, isEmpty);
    expect(find.text('El teléfono debe tener 10 dígitos.'), findsOneWidget);
    await t.enterText(
      find.widgetWithText(TextField, 'Teléfono bancario (10 dígitos)'),
      '5512345678',
    );
    await pulsar(t, 'Cobrar');
    expect(
      repo.solicitudes.single['telefono_bancario_confirmado'],
      '5512345678',
    );
    expect(repo.solicitudes.single['canal'], 'notificacion');
  });

  testWidgets('400 de push muestra error en telefono y deja editar', (t) async {
    final repo = RepoAcciones()..errorAccion = error('PAYLOAD_INVALIDO', 400);
    await abrir(t, repo);
    await t.tap(find.byType(DropdownButton<String>).first);
    await t.pumpAndSettle();
    await t.tap(find.text('Enviar al celular').last);
    await t.pumpAndSettle();
    await t.enterText(
      find.widgetWithText(TextField, 'Teléfono bancario (10 dígitos)'),
      '5512345678',
    );
    await pulsar(t, 'Cobrar');
    final telefono = t.widget<TextField>(
      find.widgetWithText(TextField, 'Teléfono bancario (10 dígitos)'),
    );
    expect(telefono.decoration!.errorText, 'Revisa el teléfono bancario.');
    expect(telefono.enabled, isTrue);
    expect(
      t
          .widget<FilledButton>(find.widgetWithText(FilledButton, 'Cobrar'))
          .onPressed,
      isNotNull,
    );
  });

  testWidgets('activar espera envia intento y accion', (t) async {
    final repo = RepoAcciones()..pago = 'en_espera';
    await abrir(t, repo);
    await pulsar(t, 'Activar cobro');
    expect(repo.solicitudes.single['accion'], 'activar_espera');
    expect(repo.solicitudes.single['intento_id'], 'i1');
  });
  testWidgets('listo y entregado muestran actor y cierran', (t) async {
    final repo = RepoAcciones()..pago = 'pagado';
    await abrir(t, repo);
    await pulsar(t, 'Marcar listo');
    expect(repo.solicitudes.single['ruta'], 'listo');
    expect(find.text('Listo'), findsOneWidget);
    expect(find.textContaining('Ana'), findsOneWidget);
    expect(find.textContaining('2026-01-01'), findsOneWidget);
    await pulsar(t, 'Marcar entregado');
    expect(repo.solicitudes.last['ruta'], 'entregado');
    expect(
      repo.solicitudes.first['command_key'],
      isNot(repo.solicitudes.last['command_key']),
    );
    expect(find.text('Entregado'), findsOneWidget);
    expect(find.text('Marcar entregado'), findsNothing);
  });
  testWidgets('doble toque en listo no envia dos veces', (t) async {
    final repo = RepoAcciones()
      ..pago = 'pagado'
      ..demora = Completer<void>();
    await abrir(t, repo);
    await t.tap(find.text('Marcar listo'));
    await t.pump();
    expect(
      t
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Marcar listo'),
          )
          .onPressed,
      isNull,
    );
    expect(repo.solicitudes.length, 1);
    repo.demora!.complete();
    await t.pump();
  });
  for (final codigo in ['VERSION_OBSOLETA', 'CLAVE_REUTILIZADA']) {
    testWidgets('$codigo en listo recarga y limpia clave', (t) async {
      final repo = RepoAcciones()
        ..pago = 'pagado'
        ..errorAccion = error(codigo, 409);
      await abrir(t, repo);
      await pulsar(t, 'Marcar listo');
      expect(repo.lecturas, 2);
      repo.errorAccion = null;
      await pulsar(t, 'Marcar listo');
      expect(
        repo.solicitudes.first['command_key'],
        isNot(repo.solicitudes.last['command_key']),
      );
    });
  }
  for (final codigo in ['RED', 'SERVICIO_NO_DISPONIBLE']) {
    testWidgets('$codigo en listo conserva clave y permite reintento', (
      t,
    ) async {
      final repo = RepoAcciones()
        ..pago = 'pagado'
        ..errorAccion = error(codigo, codigo == 'RED' ? null : 503);
      await abrir(t, repo);
      await pulsar(t, 'Marcar listo');
      expect(find.text(codigo), findsOneWidget);
      repo.errorAccion = null;
      await pulsar(t, 'Marcar listo');
      expect(
        repo.solicitudes.first['command_key'],
        repo.solicitudes.last['command_key'],
      );
    });
  }
  for (final codigo in [
    'PAYLOAD_INVALIDO',
    'PAGO_NO_CONFIRMADO',
    'PREPARACION_INVALIDA',
  ]) {
    testWidgets('$codigo en listo muestra mensaje y habilita formulario', (
      t,
    ) async {
      final repo = RepoAcciones()
        ..pago = 'pagado'
        ..errorAccion = error(codigo, codigo == 'PAYLOAD_INVALIDO' ? 400 : 409);
      await abrir(t, repo);
      await pulsar(t, 'Marcar listo');
      expect(find.text(codigo), findsOneWidget);
      expect(
        t
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Marcar listo'),
            )
            .onPressed,
        isNotNull,
      );
    });
  }
  for (final status in [401, 403]) {
    testWidgets('$status en listo oculta acciones', (t) async {
      final repo = RepoAcciones()
        ..pago = 'pagado'
        ..errorAccion = error('PERMISO_DENEGADO', status);
      await abrir(t, repo);
      await pulsar(t, 'Marcar listo');
      expect(find.text('PERMISO_DENEGADO'), findsOneWidget);
      expect(find.text('Marcar listo'), findsNothing);
    });
  }
  testWidgets('404 en entregado ofrece volver', (t) async {
    final repo = RepoAcciones()
      ..pago = 'pagado'
      ..preparacion = 'listo'
      ..errorAccion = error('PEDIDO_NO_ACCESIBLE', 404);
    await abrir(t, repo);
    await pulsar(t, 'Marcar entregado');
    expect(find.text('Volver a pedidos'), findsOneWidget);
    expect(find.text('Marcar entregado'), findsNothing);
  });
  for (final codigo in [
    'CUENTA_NO_ACTIVE',
    'DEMO_DESTINO_NO_PERMITIDO',
    'MODO_CAMBIO',
    'ACEPTACION_REQUERIDA',
    'PROVEEDOR_NO_DISPONIBLE',
  ]) {
    testWidgets('$codigo en cobro muestra aviso', (t) async {
      final repo = RepoAcciones()
        ..errorAccion = error(
          codigo,
          codigo == 'PROVEEDOR_NO_DISPONIBLE' ? 503 : 409,
        );
      await abrir(t, repo);
      await pulsar(t, 'Cobrar');
      expect(find.text(codigo), findsOneWidget);
      expect(repo.solicitudes.length, 1);
    });
  }
  for (final codigo in ['RED', 'SERVICIO_NO_DISPONIBLE']) {
    testWidgets('$codigo en cobro bloquea repeticion ciega', (t) async {
      final repo = RepoAcciones()
        ..errorAccion = error(codigo, codigo == 'RED' ? null : 503);
      await abrir(t, repo);
      await pulsar(t, 'Cobrar');
      expect(
        find.text('No sabemos si se generó el cobro; no lo repitas.'),
        findsOneWidget,
      );
      expect(find.text('Cobrar'), findsNothing);
      expect(repo.solicitudes.length, 1);
    });
  }
  for (final codigo in ['VERSION_OBSOLETA', 'CLAVE_REUTILIZADA']) {
    testWidgets('$codigo en cobro recarga y cambia clave', (t) async {
      final repo = RepoAcciones()..errorAccion = error(codigo, 409);
      await abrir(t, repo);
      await pulsar(t, 'Cobrar');
      expect(repo.lecturas, 2);
      repo.errorAccion = null;
      await pulsar(t, 'Cobrar');
      expect(
        repo.solicitudes.first['command_key'],
        isNot(repo.solicitudes.last['command_key']),
      );
    });
  }
  for (final status in [401, 403, 404]) {
    testWidgets('$status en carga oculta acciones', (t) async {
      final repo = RepoAcciones()
        ..errorCarga = error(
          status == 404 ? 'PEDIDO_NO_ACCESIBLE' : 'PERMISO_DENEGADO',
          status,
        );
      await abrir(t, repo);
      expect(find.text('Cobrar'), findsNothing);
      expect(find.text('Guardar renglones'), findsNothing);
      if (status == 404) expect(find.text('Volver a pedidos'), findsOneWidget);
    });
  }
}
