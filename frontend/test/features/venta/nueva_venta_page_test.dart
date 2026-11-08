import 'package:cody/core/router/app_router.dart';
import 'package:cody/features/cobro/presentation/qr_general_impreso_page.dart';
import 'package:cody/features/venta/data/venta_repository.dart';
import 'package:cody/features/venta/presentation/nueva_venta_page.dart';
import 'package:cody/features/venta/presentation/venta_espera_page.dart';
import 'package:cody/features/venta/presentation/venta_providers.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

import '../../support/mock_venta_api.dart';
import '../../support/override_cuenta_estado.dart';

Future<void> _montar(WidgetTester tester, MockVentaApi mock) async {
  final repositorio = VentaRepository(mock.dio);
  final router = GoRouter(
    initialLocation: kRutaNuevaVenta,
    routes: [
      GoRoute(
        path: kRutaNuevaVenta,
        builder: (context, state) => NuevaVentaPage(repositorio: repositorio),
      ),
      GoRoute(
        path: '/venta/:id',
        builder: (context, state) {
          final id = int.parse(state.pathParameters['id']!);
          return VentaEsperaPage(
            movimientoId: id,
            avisoPendiente: state.uri.queryParameters['aviso'] == 'pendiente',
            repositorio: repositorio,
          );
        },
      ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        ventaRepositoryProvider.overrideWith(
          (ref) => VentaRepository(mock.dio),
        ),
        cuentaEstadoActivaOverride(),
      ],
      child: MaterialApp.router(theme: TfTheme.light, routerConfig: router),
    ),
  );
  await tester.pump();
}

Future<void> _monto(WidgetTester tester, String valor) {
  return tester.enterText(find.byKey(const Key('campo_monto')), valor);
}

Future<void> _cobrar(WidgetTester tester) async {
  await tester.tap(find.byKey(const Key('boton_cobrar')));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 1));
  await tester.pump(const Duration(milliseconds: 1));
  await tester.pump(const Duration(milliseconds: 1));
  await tester.pump(const Duration(milliseconds: 1));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 1));
  await tester.pump(const Duration(milliseconds: 1));
  await tester.pump(const Duration(milliseconds: 1));
  await tester.pump(const Duration(milliseconds: 1));
  await tester.pump();
}

void main() {
  testWidgets('monto vacío, cero, de más de 2 decimales o letras no piden', (
    tester,
  ) async {
    final mock = MockVentaApi(crearDioVenta());
    await _montar(tester, mock);

    await _cobrar(tester);
    expect(find.text('Escribe el monto.'), findsOneWidget);
    expect(mock.peticiones, isEmpty);

    await _monto(tester, '0');
    await _cobrar(tester);
    expect(find.text('El monto debe ser mayor que 0.'), findsOneWidget);

    await _monto(tester, '1.234');
    await _cobrar(tester);
    expect(find.text('El monto no admite más de 2 decimales.'), findsOneWidget);

    await _monto(tester, 'abc');
    await _cobrar(tester);
    expect(find.text('El monto debe ser un número.'), findsOneWidget);
    expect(mock.peticiones, isEmpty);
  });

  testWidgets('referencia con letras u 8 dígitos no pide', (tester) async {
    final mock = MockVentaApi(crearDioVenta());
    await _montar(tester, mock);
    await _monto(tester, '10.00');

    await tester.enterText(find.byKey(const Key('campo_referencia')), '12a');
    await _cobrar(tester);
    expect(
      find.text('La referencia debe ser numérica, de 1 a 7 dígitos.'),
      findsOneWidget,
    );

    await tester.enterText(
      find.byKey(const Key('campo_referencia')),
      '12345678',
    );
    await _cobrar(tester);
    expect(
      find.text('La referencia debe ser numérica, de 1 a 7 dígitos.'),
      findsOneWidget,
    );
    expect(mock.peticiones, isEmpty);
  });

  testWidgets('409 de venta viva abre la espera de esa venta', (tester) async {
    final mock = MockVentaApi(crearDioVenta());
    mock.alCrear(409, {
      'detail': 'Ya hay una venta pendiente.',
      'movimiento_id': 9,
      'canal': 'qr_venta',
      'vence_en': '2026-11-08T18:00:00Z',
    });
    mock.alObtener([
      cuerpoVenta(id: 9, estado: 'pendiente', concepto: 'Tortas'),
    ]);

    await _montar(tester, mock);
    await _monto(tester, '12.50');
    await _cobrar(tester);

    expect(find.text('Ya tenías una venta pendiente'), findsOneWidget);
    expect(find.text('Tortas'), findsOneWidget);
    final aviso = tester.getRect(find.byKey(const Key('aviso_pendiente')));
    expect(aviso.left, greaterThan(120));
    expect(aviso.right, lessThan(680));
    tester.view.physicalSize = const Size(320, 700);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pump();
    expect(tester.takeException(), isNull);
    expect(find.text('Ya tenías una venta pendiente'), findsOneWidget);
    expect(mock.peticiones.map((p) => p.path), [
      rutaCrearVenta,
      '/api/ventas/9/',
    ]);
  });

  testWidgets('409 de cuenta muestra el mensaje de Mi QR', (tester) async {
    final mock = MockVentaApi(crearDioVenta());
    mock.alCrear(409, {'detail': 'La cuenta no está ACTIVE.'});

    await _montar(tester, mock);
    await _monto(tester, '12.50');
    await _cobrar(tester);

    expect(find.text(kMensajeCuentaNoActivaQr), findsOneWidget);
    expect(find.text('Cobro'), findsNothing);
  });

  testWidgets('502 con puede haberse creado avisa antes de reintentar', (
    tester,
  ) async {
    final mock = MockVentaApi(crearDioVenta());
    mock.alCrear(502, {
      'detail': 'pey no pudo crear el cobro.',
      'tipo': 'TIMEOUT',
      'request_id': 'req-1',
      'puede_haberse_creado': true,
    });

    await _montar(tester, mock);
    await _monto(tester, '12.50');
    await _cobrar(tester);

    expect(find.text('pey no pudo crear el cobro.'), findsOneWidget);
    expect(
      find.text(
        'Puede que el cobro se haya creado; revisa Movimientos antes de reintentar',
      ),
      findsOneWidget,
    );
    expect(find.text('Reintentar'), findsOneWidget);
    expect(find.text('Cobro'), findsNothing);
  });

  testWidgets('concepto viene prellenado y el botón muestra el monto', (
    tester,
  ) async {
    final mock = MockVentaApi(crearDioVenta());
    await _montar(tester, mock);

    expect(
      tester
          .widget<TextFormField>(find.byKey(const Key('campo_concepto')))
          .controller!
          .text,
      'Transferencia',
    );
    expect(find.text('Cobrar'), findsOneWidget);
    await _monto(tester, '120');
    await tester.pump();
    expect(find.text('Cobrar \$120'), findsOneWidget);
  });

  testWidgets('A su celular pide 10 dígitos y usa la notificación', (
    tester,
  ) async {
    final mock = MockVentaApi(crearDioVenta());
    mock.alCrearNotificacion(
      201,
      cuerpoNotificacion(
        id: 11,
        venceEn: DateTime.now()
            .toUtc()
            .add(const Duration(minutes: 5))
            .toIso8601String(),
      ),
    );
    mock.alObtener([
      cuerpoVenta(
        id: 11,
        estado: 'pendiente',
        canal: 'notificacion',
        qrString: '',
        concepto: 'Transferencia',
      ),
    ]);
    await _montar(tester, mock);
    expect(find.byKey(const Key('campo_celular')), findsNothing);
    await tester.tap(find.text('A su celular'));
    await tester.pump();
    await _monto(tester, '120');
    await tester.enterText(find.byKey(const Key('campo_celular')), '55123');
    await _cobrar(tester);
    expect(
      find.text('Revisa el celular: deben ser 10 dígitos.'),
      findsOneWidget,
    );
    expect(mock.peticiones, isEmpty);

    await tester.enterText(
      find.byKey(const Key('campo_celular')),
      '5512344321',
    );
    await _cobrar(tester);
    expect(mock.peticiones.map((p) => p.path), [
      rutaCrearNotificacion,
      '/api/ventas/11/',
    ]);
    expect(find.textContaining('terminado en 4321'), findsOneWidget);
  });
}
