import 'package:cody/core/fecha/dia_cdmx.dart';
import 'package:cody/core/network/providers.dart';
import 'package:cody/core/router/app_router.dart';
import 'package:cody/core/sesion/sesion_models.dart';
import 'package:cody/core/sesion/sesion_notifier.dart';
import 'package:cody/core/sesion/sesion_view_state.dart';
import 'package:cody/features/inicio/presentation/inicio_widgets.dart';
import 'package:cody/features/sesion/presentation/home_autenticado_page.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

import '../../support/mock_inicio_api.dart';
import '../../support/override_cuenta_estado.dart';
import '../../support/mock_sesion_api.dart';

class _SesionSinNombre extends SesionNotifier {
  @override
  SesionViewState build() => const SesionViewState(
    resuelto: true,
    cargando: false,
    estado: EstadoSesion(
      usuario: 'demo',
      correo: 'demo@cody.mx',
      nombre: '',
      apellidos: '',
      comercio: ComercioResumen(id: 1, nombre: 'Abarrotes Demo'),
    ),
  );
}

class _SesionFija extends SesionNotifier {
  @override
  SesionViewState build() => const SesionViewState(
    resuelto: true,
    cargando: false,
    estado: EstadoSesion(
      usuario: 'lupe',
      correo: 'lupe@tortilleria.mx',
      nombre: 'Lupe',
      apellidos: 'García',
      comercio: ComercioResumen(id: 1, nombre: 'Tortillería La Esperanza'),
    ),
  );
}

String _hoyIso(int hora) {
  // `hora` es hora de CDMX (UTC−6 fijo).
  final h = ahoraCdmx();
  return DateTime.utc(h.year, h.month, h.day, hora + 6).toIso8601String();
}

/// [dia] es un día civil de CDMX; [hora] y [minuto] son de ese reloj.
String _isoCdmx(DateTime dia, int hora, [int minuto = 0]) {
  return DateTime.utc(
    dia.year,
    dia.month,
    dia.day,
    hora + 6,
    minuto,
  ).toIso8601String();
}

Future<void> _montar(
  WidgetTester tester,
  Dio dio, {
  SesionNotifier Function()? sesion,
  Size superficie = const Size(800, 1800),
}) async {
  tester.view.physicalSize = superficie;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final rutas = <String>[];
  final router = GoRouter(
    initialLocation: kRutaInicio,
    routes: [
      GoRoute(
        path: kRutaInicio,
        builder: (context, state) => const HomeAutenticadoPage(),
      ),
      for (final r in [kRutaNuevaVenta, kRutaMiQr, kRutaMovimientos])
        GoRoute(
          path: r,
          builder: (context, state) {
            rutas.add(r);
            return Scaffold(body: Text('destino $r'));
          },
        ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        dioProvider.overrideWithValue(dio),
        cuentaEstadoActivaOverride(),
        sesionNotifierProvider.overrideWith(sesion ?? _SesionFija.new),
      ],
      child: MaterialApp.router(theme: TfTheme.light, routerConfig: router),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 100));
}

void main() {
  group('saludoInicio', () {
    test('con nombre saluda por el nombre', () {
      expect(saludoInicio('Lupe'), 'Hola, Lupe');
    });

    test('un correo no se usa como nombre', () {
      expect(saludoInicio('demo@cody.mx'), 'Hola');
      expect(saludoInicio('  '), 'Hola');
    });
  });

  group('cuandoCobro', () {
    // 8 nov 2026, 12:00 en CDMX.
    final ahora = DateTime.utc(2026, 11, 8, 18);

    test('hoy solo muestra la hora', () {
      expect(
        cuandoCobro(DateTime.utc(2026, 11, 9, 0, 20), ahora: ahora),
        '18:20',
      );
    });

    test('ayer antepone Ayer', () {
      expect(
        cuandoCobro(DateTime.utc(2026, 11, 8, 0, 20), ahora: ahora),
        'Ayer 18:20',
      );
    });

    test('otro día antepone el día', () {
      expect(
        cuandoCobro(DateTime.utc(2026, 11, 6, 0, 20), ahora: ahora),
        'Jue 05 nov 18:20',
      );
    });
  });

  testWidgets('muestra el resumen de hoy y los últimos cobros', (tester) async {
    final dio = crearDioPrueba();
    instalarInicioApi(
      dio,
      totalHoy: '1250.50',
      cobrosHoy: 2,
      movimientos: [
        for (var i = 1; i <= 4; i++)
          {
            'id': 400 + i,
            'monto': '10.00',
            'concepto_visible': 'Venta $i',
            'canal': 'qr_general',
            'estado': i == 1 ? 'pendiente' : 'pagado',
            'origen': 'origen_pey',
            'creado_en': _hoyIso(8 + i),
            'pagado_en': i == 1 ? null : _hoyIso(8 + i),
          },
      ],
    );
    await _montar(tester, dio);

    expect(find.text('Hola, Lupe'), findsOneWidget);
    final saludo = tester.widget<Text>(find.text('Hola, Lupe'));
    expect(saludo.maxLines, 1);
    expect(saludo.overflow, TextOverflow.ellipsis);
    expect(
      tester.getSize(find.byType(Card).first).width,
      lessThanOrEqualTo(480),
    );
    expect(find.text('Tortillería La Esperanza'), findsOneWidget);
    expect(find.text('Hoy llevas'), findsOneWidget);
    expect(find.text(r'$1,250.50'), findsOneWidget);
    expect(find.textContaining('2 cobros'), findsOneWidget);
    expect(find.textContaining('1 pendiente'), findsOneWidget);
    expect(find.text('ÚLTIMOS COBROS'), findsOneWidget);
    // Solo los tres más recientes.
    expect(find.text('Venta 4'), findsOneWidget);
    expect(find.text('Venta 3'), findsOneWidget);
    expect(find.text('Venta 2'), findsOneWidget);
    expect(find.text('Venta 1'), findsNothing);
    expect(find.text('Salir'), findsNothing);
    expect(find.text('Ver movimientos'), findsNothing);
  });

  testWidgets('sin datos muestra \$0.00 y estado vacío', (tester) async {
    final dio = crearDioPrueba();
    instalarInicioApi(dio);
    await _montar(tester, dio);

    expect(find.text(r'$0.00'), findsOneWidget);
    expect(find.textContaining('0 cobros'), findsOneWidget);
    expect(find.textContaining('Aún no hay cobros'), findsOneWidget);
  });

  testWidgets('un error muestra aviso con Reintentar', (tester) async {
    final dio = crearDioPrueba();
    await _montar(tester, dio);

    expect(find.text('Reintentar'), findsOneWidget);
    expect(find.text('Cobrar'), findsOneWidget);
  });

  testWidgets('sin nombre el saludo no muestra el correo', (tester) async {
    final dio = crearDioPrueba();
    instalarInicioApi(dio);
    await _montar(
      tester,
      dio,
      sesion: _SesionSinNombre.new,
      superficie: const Size(320, 640),
    );

    expect(find.text('Hola'), findsOneWidget);
    expect(find.textContaining('demo@cody.mx'), findsNothing);
    expect(find.textContaining('@'), findsNothing);
  });

  testWidgets('un cobro de otro día muestra el día y hoy solo la hora', (
    tester,
  ) async {
    final hoy = diaCdmx(DateTime.now());
    final ayer = DateTime(hoy.year, hoy.month, hoy.day - 1);
    final antes = DateTime(hoy.year, hoy.month, hoy.day - 3);
    final dio = crearDioPrueba();
    instalarInicioApi(
      dio,
      movimientos: [
        {
          'id': 1,
          'monto': '10.00',
          'concepto_visible': 'De hoy',
          'canal': 'notificacion',
          'estado': 'pagado',
          'origen': 'origen_pey',
          'creado_en': _isoCdmx(hoy, 9, 20),
          'pagado_en': _isoCdmx(hoy, 9, 20),
        },
        {
          'id': 2,
          'monto': '20.00',
          'concepto_visible': 'De ayer',
          'canal': 'qr_venta',
          'estado': 'pagado',
          'origen': 'origen_pey',
          'creado_en': _isoCdmx(ayer, 18, 20),
          'pagado_en': _isoCdmx(ayer, 18, 20),
        },
        {
          'id': 3,
          'monto': '30.00',
          'concepto_visible': 'De antes',
          'canal': 'qr_general',
          'estado': 'pagado',
          'origen': 'origen_pey',
          'creado_en': _isoCdmx(antes, 18, 20),
          'pagado_en': _isoCdmx(antes, 18, 20),
        },
      ],
    );
    await _montar(tester, dio);

    expect(find.text('09:20 · Notificación'), findsOneWidget);
    expect(find.text('Ayer 18:20 · QR de venta'), findsOneWidget);
    final antiguo = cuandoCobro(DateTime.parse(_isoCdmx(antes, 18, 20)));
    expect(find.text('$antiguo · QR general'), findsOneWidget);
    expect(antiguo.contains('Ayer'), isFalse);
  });

  testWidgets('Mi QR navega a su pantalla', (tester) async {
    final dio = crearDioPrueba();
    instalarInicioApi(dio);
    await _montar(tester, dio);

    await tester.tap(find.text('Mi QR'));
    await tester.pumpAndSettle();
    expect(find.text('destino $kRutaMiQr'), findsOneWidget);
  });
}
