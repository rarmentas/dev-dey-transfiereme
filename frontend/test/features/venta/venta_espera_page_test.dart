import 'package:cody/features/venta/data/venta.dart';
import 'package:cody/features/venta/data/venta_repository.dart';
import 'package:cody/features/venta/presentation/venta_espera_page.dart';
import 'package:cody/features/venta/presentation/venta_providers.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../support/mock_venta_api.dart';

Future<void> _montar(WidgetTester tester, MockVentaApi mock, int id) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        ventaRepositoryProvider.overrideWith(
          (ref) => VentaRepository(mock.dio),
        ),
      ],
      child: MaterialApp(
        theme: TfTheme.light,
        home: VentaEsperaPage(
          movimientoId: id,
          repositorio: VentaRepository(mock.dio),
        ),
      ),
    ),
  );
  // Dio agenda cada interceptor en un temporizador de duración cero.
  await _cerrarRed(tester);
}

Future<void> _cerrarRed(WidgetTester tester) async {
  await tester.pump(const Duration(milliseconds: 1));
  await tester.pump(const Duration(milliseconds: 1));
  await tester.pump(const Duration(milliseconds: 1));
  await tester.pump(const Duration(milliseconds: 1));
  await tester.pump();
}

void main() {
  test('el mock responde obtener', () async {
    final mock = MockVentaApi(crearDioVenta());
    mock.alObtener([cuerpoVenta(id: 4, estado: 'pendiente')]);
    final venta = await VentaRepository(mock.dio).obtener(4);
    expect(venta.estado, 'pendiente');
    expect(mock.lecturas, 1);
  });

  testWidgets('pendiente y luego vencido deja de consultar', (tester) async {
    final mock = MockVentaApi(crearDioVenta());
    final vence = DateTime.now().toUtc().add(const Duration(minutes: 8));
    mock.alObtener([
      cuerpoVenta(id: 4, estado: 'pendiente', venceEn: vence.toIso8601String()),
      cuerpoVenta(id: 4, estado: 'vencido', venceEn: vence.toIso8601String()),
    ]);

    await _montar(tester, mock, 4);

    expect(find.byType(QrImageView), findsOneWidget);
    expect(find.text('Tacos'), findsOneWidget);
    expect(mock.lecturas, 1);

    await tester.pump(const Duration(seconds: 2));
    await _cerrarRed(tester);

    expect(find.text('Este cobro venció'), findsOneWidget);
    expect(find.textContaining('venció'), findsOneWidget);
    expect(find.byType(QrImageView), findsNothing);
    expect(mock.lecturas, 2);

    await tester.pump(const Duration(seconds: 2));
    await tester.pump();
    expect(mock.lecturas, 2);
  });

  testWidgets('pendiente y luego pagado muestra la confirmación', (
    tester,
  ) async {
    final mock = MockVentaApi(crearDioVenta());
    const pagadoEn = '2026-11-08T18:30:00Z';
    mock.alObtener([
      cuerpoVenta(id: 5, estado: 'pendiente', qrString: 'QR-PAGO'),
      cuerpoVenta(id: 5, estado: 'pagado', pagadoEn: pagadoEn, qrString: ''),
    ]);

    await _montar(tester, mock, 5);
    expect(mock.lecturas, 1);

    await tester.pump(const Duration(seconds: 2));
    await _cerrarRed(tester);

    expect(find.text('¡Te pagaron!'), findsOneWidget);
    expect(find.text(horaLocalCorta(DateTime.parse(pagadoEn))), findsOneWidget);
    expect(find.text('Nuevo cobro'), findsOneWidget);
    expect(find.text('Listo'), findsOneWidget);
    expect(mock.lecturas, 2);

    await tester.pump(const Duration(seconds: 2));
    expect(mock.lecturas, 2);
  });

  testWidgets('al salir de la pantalla el temporizador se cancela', (
    tester,
  ) async {
    final mock = MockVentaApi(crearDioVenta());
    mock.alObtener([cuerpoVenta(id: 6, estado: 'pendiente')]);

    await _montar(tester, mock, 6);
    expect(mock.lecturas, 1);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(seconds: 3));
    expect(mock.lecturas, 1);
  });

  testWidgets('vencido ofrece generar otro igual', (tester) async {
    final mock = MockVentaApi(crearDioVenta());
    mock.alObtener([cuerpoVenta(id: 7, estado: 'vencido', monto: '120.00')]);
    await _montar(tester, mock, 7);
    expect(find.text('Puedes generar otro igual.'), findsOneWidget);
    expect(find.text('Generar otro igual'), findsOneWidget);
  });

  testWidgets('pendiente muestra Vence en y el texto para escanear', (
    tester,
  ) async {
    final mock = MockVentaApi(crearDioVenta());
    final vence = DateTime.now().toUtc().add(const Duration(minutes: 5));
    mock.alObtener([
      cuerpoVenta(id: 8, estado: 'pendiente', venceEn: vence.toIso8601String()),
    ]);
    await _montar(tester, mock, 8);
    expect(find.text('Vence en'), findsOneWidget);
    expect(find.text('Pídele que escanee con la app de su banco'),
        findsOneWidget);
    expect(find.byTooltip('Cerrar'), findsOneWidget);
  });
}
