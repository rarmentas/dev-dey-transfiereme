import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:cody/features/pedidos/data/pedido.dart';
import 'package:cody/features/pedidos/data/pedido_repository.dart';
import 'package:cody/features/pedidos/presentation/pedido_detalle_page.dart';
import 'package:cody/features/pedidos/presentation/pedido_providers.dart';

import '../../support/mock_pedido_api.dart';

class RepoPrueba extends PedidoRepository {
  RepoPrueba() : super(crearDioPedido());
  PedidoException? error;
  bool cotizado = false;
  bool aceptado = false;
  bool cancelado = false;
  int lecturas = 0;
  String pagoEstado = 'sin_cobro';
  bool cobroEnCurso = false;
  int version = 1;
  Completer<void>? espera;
  final cuerpos = <Map<String, dynamic>>[];
  @override
  Future<Pedido> obtener(String id) async {
    lecturas++;
    if (error?.codigo == 'PEDIDO_NO_ACCESIBLE') throw error!;
    final json = pedidoJson(
      cotizado: cotizado,
      aceptado: aceptado,
      version: version,
    );
    json['pago_estado'] = pagoEstado;
    json['cobro_en_curso'] =
        cobroEnCurso ||
        {'enviando', 'pendiente', 'incierto'}.contains(pagoEstado);
    if (cancelado) json['estado'] = 'cerrado';
    return Pedido.fromJson(json);
  }

  @override
  Future<Pedido> revisar(String id, Map<String, dynamic> cuerpo) async {
    cuerpos.add(cuerpo);
    if (espera != null) await espera!.future;
    if (error != null) throw error!;
    version++;
    return obtener(id);
  }

  @override
  Future<Pedido> publicar(String id, Map<String, dynamic> cuerpo) async {
    cuerpos.add(cuerpo);
    if (error != null) throw error!;
    cotizado = true;
    version++;
    return obtener(id);
  }

  @override
  Future<Pedido> cancelar(String id, Map<String, dynamic> cuerpo) async {
    cuerpos.add(cuerpo);
    if (error != null) throw error!;
    cancelado = true;
    version++;
    return obtener(id);
  }
}

Future<void> abrir(WidgetTester tester, RepoPrueba repo) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [pedidoRepositoryProvider.overrideWithValue(repo)],
      child: const MaterialApp(home: PedidoDetallePage(id: 'abc')),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> tocar(WidgetTester tester, String texto) async {
  await tester.scrollUntilVisible(
    find.text(texto),
    250,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.tap(find.text(texto));
  await tester.pumpAndSettle();
}

PedidoException fallo(
  String codigo, {
  Map<String, dynamic> errores = const {},
}) => PedidoException(codigo, 409, codigo, errores: errores);
void main() {
  testWidgets('confirma cancelación y envía versión y clave', (t) async {
    final r = RepoPrueba();
    await abrir(t, r);
    await tocar(t, 'Cancelar pedido');
    expect(find.text('Confirmar cancelación'), findsOneWidget);
    await t.tap(find.text('Confirmar cancelación'));
    await t.pumpAndSettle();
    expect(r.cuerpos.single['expected_version'], 1);
    expect(r.cuerpos.single['command_key'], isNotEmpty);
    await t.scrollUntilVisible(
      find.text('Pedido cancelado. El cliente puede enviar uno nuevo.'),
      -250,
      scrollable: find.byType(Scrollable).first,
    );
    expect(
      find.text('Pedido cancelado. El cliente puede enviar uno nuevo.'),
      findsOneWidget,
    );
    expect(find.text('Cancelar pedido'), findsNothing);
  });

  testWidgets('no permite cancelar con cobro en curso', (t) async {
    final r = RepoPrueba()
      ..pagoEstado = 'en_espera'
      ..cobroEnCurso = true;
    await abrir(t, r);
    await t.scrollUntilVisible(
      find.text('Cancelar pedido'),
      250,
      scrollable: find.byType(Scrollable).first,
    );
    final boton = t.widget<OutlinedButton>(
      find.widgetWithText(OutlinedButton, 'Cancelar pedido'),
    );
    expect(boton.onPressed, isNull);
  });

  testWidgets('I6 polling en espera conserva borrador y lo guarda', (t) async {
    final r = RepoPrueba()..pagoEstado = 'en_espera';
    await t.pumpWidget(
      ProviderScope(
        overrides: [pedidoRepositoryProvider.overrideWithValue(r)],
        child: const MaterialApp(home: PedidoDetallePage(id: 'abc')),
      ),
    );
    await t.pump();
    await t.pump();
    await t.ensureVisible(find.widgetWithText(TextFormField, 'Cantidad'));
    await t.enterText(find.widgetWithText(TextFormField, 'Cantidad'), '3');
    await t.pump(const Duration(seconds: 2));
    await t.pump();
    expect(r.lecturas, 2);
    expect(
      t
          .widget<EditableText>(
            find.descendant(
              of: find.widgetWithText(TextFormField, 'Cantidad'),
              matching: find.byType(EditableText),
            ),
          )
          .controller
          .text,
      '3',
    );
    await t.ensureVisible(find.text('Guardar renglones'));
    await t.tap(find.text('Guardar renglones'));
    await t.pump();
    expect((r.cuerpos.single['renglones'] as List).single['cantidad'], '3');
    await t.pumpWidget(const SizedBox());
  });

  testWidgets('I6 version remota cambiada conserva borrador y exige recargar', (
    t,
  ) async {
    final r = RepoPrueba()..pagoEstado = 'en_espera';
    await t.pumpWidget(
      ProviderScope(
        overrides: [pedidoRepositoryProvider.overrideWithValue(r)],
        child: const MaterialApp(home: PedidoDetallePage(id: 'abc')),
      ),
    );
    await t.pump();
    await t.pump();
    await t.ensureVisible(find.widgetWithText(TextFormField, 'Cantidad'));
    await t.enterText(find.widgetWithText(TextFormField, 'Cantidad'), '3');
    r.version = 2;
    await t.pump(const Duration(seconds: 2));
    await t.pump();
    expect(
      t
          .widget<EditableText>(
            find.descendant(
              of: find.widgetWithText(TextFormField, 'Cantidad'),
              matching: find.byType(EditableText),
            ),
          )
          .controller
          .text,
      '3',
    );
    await t.ensureVisible(find.text('Guardar renglones'));
    expect(
      t
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Guardar renglones'),
          )
          .onPressed,
      isNull,
    );
    await t.scrollUntilVisible(
      find.text('Recargar pedido'),
      -250,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Recargar pedido'), findsOneWidget);
    expect(r.cuerpos, isEmpty);
    await t.tap(find.text('Recargar pedido'));
    await t.pump();
    await t.pump();
    expect(r.lecturas, 3);
    await t.ensureVisible(find.widgetWithText(TextFormField, 'Cantidad'));
    expect(
      t
          .widget<EditableText>(
            find.descendant(
              of: find.widgetWithText(TextFormField, 'Cantidad'),
              matching: find.byType(EditableText),
            ),
          )
          .controller
          .text,
      '1',
    );
    await t.pumpWidget(const SizedBox());
  });

  testWidgets('I6 conflicto al guardar no borra cambios del borrador', (
    t,
  ) async {
    final r = RepoPrueba()
      ..pagoEstado = 'en_espera'
      ..error = fallo('VERSION_OBSOLETA');
    await t.pumpWidget(
      ProviderScope(
        overrides: [pedidoRepositoryProvider.overrideWithValue(r)],
        child: const MaterialApp(home: PedidoDetallePage(id: 'abc')),
      ),
    );
    await t.pump();
    await t.pump();
    await t.ensureVisible(find.widgetWithText(TextFormField, 'Cantidad'));
    await t.enterText(find.widgetWithText(TextFormField, 'Cantidad'), '4');
    await t.ensureVisible(find.text('Guardar renglones'));
    await t.tap(find.text('Guardar renglones'));
    await t.pump();
    expect(r.lecturas, 1);
    expect(
      t
          .widget<EditableText>(
            find.descendant(
              of: find.widgetWithText(TextFormField, 'Cantidad'),
              matching: find.byType(EditableText),
            ),
          )
          .controller
          .text,
      '4',
    );
    expect(
      t
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Guardar renglones'),
          )
          .onPressed,
      isNull,
    );
    await t.pumpWidget(const SizedBox());
  });

  testWidgets('polling solo con estados vivos y se cancela', (t) async {
    final repo = RepoPrueba()..pagoEstado = 'pendiente';
    await t.pumpWidget(
      ProviderScope(
        overrides: [pedidoRepositoryProvider.overrideWithValue(repo)],
        child: const MaterialApp(home: PedidoDetallePage(id: 'abc')),
      ),
    );
    await t.pump();
    expect(repo.lecturas, 1);
    await t.pump(const Duration(seconds: 2));
    await t.pump();
    expect(repo.lecturas, 2);
    repo.pagoEstado = 'pagado';
    await t.pump(const Duration(seconds: 2));
    await t.pump();
    expect(repo.lecturas, 3);
    await t.pump(const Duration(seconds: 4));
    expect(repo.lecturas, 3);
    await t.pumpWidget(const SizedBox());
    await t.pump(const Duration(seconds: 4));
    expect(repo.lecturas, 3);
  });

  testWidgets('B3 muestra cantidad y unidad solicitadas en el detalle', (
    t,
  ) async {
    final json = pedidoJson();
    final renglon = (json['renglones'] as List).single as Map<String, dynamic>;
    renglon['texto_solicitado'] = 'tomate';
    renglon['cantidad_solicitada'] = '2';
    renglon['unidad_solicitada'] = 'kg';
    final mock = MockPedidoApi(crearDioPedido());
    mock.responder('GET', '/api/pedidos/abc/', 200, exito(json));
    await t.pumpWidget(
      ProviderScope(
        overrides: [
          pedidoRepositoryProvider.overrideWithValue(
            PedidoRepository(mock.dio),
          ),
        ],
        child: const MaterialApp(home: PedidoDetallePage(id: 'abc')),
      ),
    );
    await t.pumpAndSettle();
    expect(find.text('Solicitado: 2 kg · tomate'), findsOneWidget);
  });
  testWidgets('B3 muestra solo el texto cuando no hay cantidad ni unidad', (
    t,
  ) async {
    await abrir(t, RepoPrueba());
    expect(find.text('Solicitado: Leche'), findsOneWidget);
  });
  testWidgets('publica y muestra importes del servidor', (t) async {
    final r = RepoPrueba();
    await abrir(t, r);
    await tocar(t, 'Publicar cotización');
    expect(find.text('Total comercial: \$12.50'), findsOneWidget);
    expect(find.text('En demo se cobrará \$0.01'), findsOneWidget);
    expect(
      r.cuerpos.single.keys,
      unorderedEquals(['command_key', 'expected_version']),
    );
  });
  testWidgets('muestra aceptación y cobro cerrado', (t) async {
    final r = RepoPrueba()
      ..cotizado = true
      ..aceptado = true;
    await abrir(t, r);
    expect(
      find.text('Aceptada por el cliente (ACEPTAR P7-R2)'),
      findsOneWidget,
    );
    expect(find.text('Cobro: no habilitado todavía'), findsOneWidget);
  });
  testWidgets('404 ofrece volver sin formulario', (t) async {
    final r = RepoPrueba()..error = fallo('PEDIDO_NO_ACCESIBLE');
    await abrir(t, r);
    expect(find.text('Volver a pedidos'), findsOneWidget);
    expect(find.text('Guardar renglones'), findsNothing);
  });
  testWidgets('400 muestra error y permite editar', (t) async {
    final r = RepoPrueba()
      ..error = fallo(
        'PAYLOAD_INVALIDO',
        errores: {
          'renglones.0.descripcion': ['Revisa descripción'],
        },
      );
    await abrir(t, r);
    await tocar(t, 'Guardar renglones');
    expect(find.text('Revisa descripción'), findsOneWidget);
    expect(
      t.widget<FilledButton>(find.byType(FilledButton)).onPressed,
      isNotNull,
    );
  });
  testWidgets('versión obsoleta recarga y permite volver a guardar', (t) async {
    final r = RepoPrueba()..error = fallo('VERSION_OBSOLETA');
    await abrir(t, r);
    await tocar(t, 'Guardar renglones');
    expect(r.lecturas, 2);
    await t.scrollUntilVisible(
      find.text('VERSION_OBSOLETA'),
      -250,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('VERSION_OBSOLETA'), findsOneWidget);
    r.error = null;
    await tocar(t, 'Guardar renglones');
    expect(r.cuerpos[0]['command_key'], isNot(r.cuerpos[1]['command_key']));
  });
  testWidgets('pendiente informa y conserva controles', (t) async {
    final r = RepoPrueba()
      ..error = fallo(
        'RENGLON_PENDIENTE',
        errores: {
          'renglones_pendientes': ['r1'],
        },
      );
    await abrir(t, r);
    await tocar(t, 'Publicar cotización');
    await t.scrollUntilVisible(
      find.text('RENGLON_PENDIENTE'),
      -250,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('RENGLON_PENDIENTE'), findsOneWidget);
    await t.scrollUntilVisible(
      find.text('Publicar cotización'),
      250,
      scrollable: find.byType(Scrollable).first,
    );
    expect(
      t
          .widget<OutlinedButton>(
            find.widgetWithText(OutlinedButton, 'Publicar cotización'),
          )
          .onPressed,
      isNotNull,
    );
  });
  testWidgets('congelado impide editar', (t) async {
    final r = RepoPrueba()..error = fallo('PEDIDO_CONGELADO');
    await abrir(t, r);
    await tocar(t, 'Guardar renglones');
    expect(find.text('Guardar renglones'), findsNothing);
    await t.scrollUntilVisible(
      find.text('PEDIDO_CONGELADO'),
      -250,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('PEDIDO_CONGELADO'), findsOneWidget);
  });
  for (final codigo in ['SERVICIO_NO_DISPONIBLE', 'RED']) {
    testWidgets('$codigo conserva clave al reintentar', (t) async {
      final r = RepoPrueba()..error = fallo(codigo);
      await abrir(t, r);
      await tocar(t, 'Guardar renglones');
      await tocar(t, 'Guardar renglones');
      expect(r.cuerpos.length, 2);
      expect(r.cuerpos[0], r.cuerpos[1]);
      expect(
        r.cuerpos.first.toString(),
        isNot(contains('total_comercial_centavos')),
      );
    });
  }
  testWidgets('clave reutilizada recarga y genera otra', (t) async {
    final r = RepoPrueba()..error = fallo('CLAVE_REUTILIZADA');
    await abrir(t, r);
    await tocar(t, 'Guardar renglones');
    r.error = null;
    await tocar(t, 'Guardar renglones');
    expect(r.lecturas, greaterThanOrEqualTo(2));
    expect(r.cuerpos[0]['command_key'], isNot(r.cuerpos[1]['command_key']));
  });
  testWidgets(
    'cambiar un campo tras fallo cambia la clave y conserva el texto',
    (t) async {
      final r = RepoPrueba()..error = fallo('SERVICIO_NO_DISPONIBLE');
      await abrir(t, r);
      await tocar(t, 'Guardar renglones');
      await t.scrollUntilVisible(
        find.text('Descripción'),
        -250,
        scrollable: find.byType(Scrollable).first,
      );
      await t.enterText(
        find.widgetWithText(TextFormField, 'Descripción'),
        'Leche nueva',
      );
      await tocar(t, 'Guardar renglones');
      expect(r.cuerpos[0]['command_key'], isNot(r.cuerpos[1]['command_key']));
      expect(
        (r.cuerpos[1]['renglones'] as List).single['descripcion'],
        'Leche nueva',
      );
    },
  );
  testWidgets('rechaza cantidad y precio con precisión inválida', (t) async {
    final r = RepoPrueba();
    await abrir(t, r);
    await t.enterText(find.widgetWithText(TextFormField, 'Cantidad'), '1.2345');
    await t.enterText(
      find.widgetWithText(TextFormField, 'Precio unitario en pesos'),
      '1.001',
    );
    await tocar(t, 'Guardar renglones');
    expect(r.cuerpos, isEmpty);
    await t.scrollUntilVisible(
      find.text('Usa una cantidad positiva con hasta 3 decimales.'),
      -250,
      scrollable: find.byType(Scrollable).first,
    );
    expect(
      find.text('Usa una cantidad positiva con hasta 3 decimales.'),
      findsOneWidget,
    );
    expect(
      find.text('Usa un precio positivo con hasta 2 decimales.'),
      findsOneWidget,
    );
  });
  testWidgets('deshabilita durante solicitud y rehabilita tras fallo', (
    t,
  ) async {
    final r = RepoPrueba()
      ..error = fallo('RED')
      ..espera = Completer<void>();
    await abrir(t, r);
    await t.scrollUntilVisible(
      find.text('Guardar renglones'),
      250,
      scrollable: find.byType(Scrollable).first,
    );
    await t.tap(find.text('Guardar renglones'));
    await t.pump();
    expect(t.widget<FilledButton>(find.byType(FilledButton)).onPressed, isNull);
    r.espera!.complete();
    await t.pumpAndSettle();
    expect(
      t.widget<FilledButton>(find.byType(FilledButton)).onPressed,
      isNotNull,
    );
  });
}
