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
  int lecturas = 0;
  int version = 1;
  Completer<void>? espera;
  final cuerpos = <Map<String, dynamic>>[];
  @override
  Future<Pedido> obtener(String id) async {
    lecturas++;
    if (error?.codigo == 'PEDIDO_NO_ACCESIBLE') throw error!;
    return Pedido.fromJson(
      pedidoJson(cotizado: cotizado, aceptado: aceptado, version: version),
    );
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
