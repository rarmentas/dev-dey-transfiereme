import 'package:cody/core/fecha/dia_cdmx.dart';
import 'package:cody/core/network/providers.dart';
import 'package:cody/core/router/app_router.dart';
import 'package:cody/core/sesion/sesion_models.dart';
import 'package:cody/core/sesion/sesion_notifier.dart';
import 'package:cody/core/sesion/sesion_view_state.dart';
import 'package:cody/features/sesion/presentation/home_autenticado_page.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

import '../../support/mock_inicio_api.dart';
import '../../support/mock_sesion_api.dart';

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

Future<void> _montar(WidgetTester tester, Dio dio) async {
  tester.view.physicalSize = const Size(800, 1800);
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
        sesionNotifierProvider.overrideWith(_SesionFija.new),
      ],
      child: MaterialApp.router(theme: TfTheme.light, routerConfig: router),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 100));
}

void main() {
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

  testWidgets('Mi QR navega a su pantalla', (tester) async {
    final dio = crearDioPrueba();
    instalarInicioApi(dio);
    await _montar(tester, dio);

    await tester.tap(find.text('Mi QR'));
    await tester.pumpAndSettle();
    expect(find.text('destino $kRutaMiQr'), findsOneWidget);
  });
}
