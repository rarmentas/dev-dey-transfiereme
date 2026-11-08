import 'package:cody/features/movimientos/data/movimiento.dart';
import 'package:cody/features/tablero/data/tablero_repository.dart';
import 'package:cody/features/tablero/presentation/tablero_page.dart';
import 'package:cody/features/tablero/presentation/tablero_providers.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/mock_tablero_api.dart';

Future<void> _montar(WidgetTester tester, MockTableroApi mock) async {
  await tester.binding.setSurfaceSize(const Size(900, 2400));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        tableroRepositoryProvider.overrideWith(
          (ref) => TableroRepository(mock.dio),
        ),
        tableroAhoraProvider.overrideWithValue(DateTime(2026, 11, 7, 20)),
      ],
      child: MaterialApp(theme: TfTheme.light, home: const TableroPage()),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 1));
  await tester.pump();
}

void _soloTablero(MockTableroApi mock) {
  expect(mock.peticiones, isNotEmpty);
  for (final peticion in mock.peticiones) {
    expect(peticion.method, 'GET');
    expect(peticion.path, rutaTableroPrueba);
    expect(peticion.path, isNot(contains('pey')));
    expect(peticion.queryParameters.keys, containsAll(['desde', 'hasta']));
  }
}

void main() {
  testWidgets('muestra cobrado y pruebas separados, sin sumarlos', (
    tester,
  ) async {
    final mock = MockTableroApi(crearDioTablero());
    mock.responderFixture();

    await _montar(tester, mock);

    _soloTablero(mock);
    // Periodo actual (esta semana) y el anterior, para la comparación.
    expect(mock.peticiones, hasLength(2));
    expect(mock.peticiones.first.queryParameters['desde'], '2026-11-02');
    expect(mock.peticiones.first.queryParameters['hasta'], '2026-11-07');
    expect(mock.peticiones.last.queryParameters['desde'], '2026-10-26');
    expect(mock.peticiones.last.queryParameters['hasta'], '2026-10-31');
    expect(find.text('Tablero'), findsOneWidget);
    expect(find.text('Esta semana'), findsOneWidget);
    expect(find.text('Lo cobrado'), findsOneWidget);
    expect(find.text('Pruebas'), findsOneWidget);
    // Total del periodo y total de pruebas, sin sumarlos.
    expect(find.text(formatearMonto('42.50')), findsOneWidget);
    expect(find.text(formatearMonto('1.01')), findsOneWidget);
    expect(find.text(formatearMonto('43.51')), findsNothing);
    // Mismo fixture en el periodo anterior: 0% de cambio.
    expect(find.textContaining('vs. semana pasada'), findsOneWidget);
    // Por canal: totales agregados por canal.
    expect(find.text('QR general'), findsOneWidget);
    expect(find.text('QR de venta'), findsOneWidget);
    expect(find.text('Notificación'), findsOneWidget);
    expect(find.text(formatearMonto('10.00')), findsOneWidget);
    expect(find.text(formatearMonto('27.50')), findsOneWidget);
    expect(find.text(formatearMonto('5.00')), findsOneWidget);
    expect(find.text('24% · 1 cobro'), findsOneWidget);
    expect(find.text('65% · 3 cobros'), findsOneWidget);
    // Por concepto.
    await tester.tap(find.text('Por concepto'));
    await tester.pump();
    expect(find.text('Tortas'), findsOneWidget);
    expect(find.text('Transferencia'), findsOneWidget);
    expect(find.text('Refrescos'), findsOneWidget);
    expect(find.text(formatearMonto('20.50')), findsOneWidget);
    expect(find.text(formatearMonto('12.00')), findsOneWidget);
    expect(find.byType(RefreshIndicator), findsOneWidget);
  });

  testWidgets('cambiar el periodo pide el rango nuevo', (tester) async {
    final mock = MockTableroApi(crearDioTablero());
    mock.responderFixture();
    await _montar(tester, mock);

    await tester.tap(find.text('Esta semana'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Este mes').last);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 1));
    await tester.pump();

    final pedidos = mock.peticiones.map((p) => p.queryParameters).toList();
    expect(
      pedidos.any((q) => q['desde'] == '2026-11-01' && q['hasta'] == '2026-11-07'),
      isTrue,
    );
    expect(
      pedidos.any((q) => q['desde'] == '2026-10-01' && q['hasta'] == '2026-10-07'),
      isTrue,
    );
  });

  testWidgets('tablero vacío muestra el texto de vacío', (tester) async {
    final mock = MockTableroApi(crearDioTablero());
    mock.responderVacio();

    await _montar(tester, mock);

    _soloTablero(mock);
    expect(find.text('Aún no tienes cobros'), findsOneWidget);
    expect(find.text('Lo cobrado'), findsNothing);
    expect(find.text('Pruebas'), findsNothing);
  });

  testWidgets('error 500 muestra mensaje y Reintentar vuelve a pedir', (
    tester,
  ) async {
    final mock = MockTableroApi(crearDioTablero());
    mock.responderError(500);

    await _montar(tester, mock);

    expect(
      find.text(
        'El servidor no está disponible en este momento. Intenta de nuevo más tarde.',
      ),
      findsOneWidget,
    );
    expect(find.text('Reintentar'), findsOneWidget);
    _soloTablero(mock);
    // Periodo actual y anterior (semana del 2 al 7 y del 26 al 31 de octubre).
    expect(mock.peticiones, hasLength(2));

    mock.responderFixture();
    await tester.tap(find.text('Reintentar'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 1));
    await tester.pump();

    // Reintentar vuelve a pedir exactamente el actual y el anterior.
    expect(mock.peticiones, hasLength(4));
    final nuevas = mock.peticiones.skip(2).map((p) => p.queryParameters);
    expect(
      nuevas.map((q) => '${q['desde']}..${q['hasta']}').toSet(),
      {'2026-11-02..2026-11-07', '2026-10-26..2026-10-31'},
    );
    _soloTablero(mock);
    expect(find.text('Lo cobrado'), findsOneWidget);
    expect(find.text(formatearMonto('42.50')), findsOneWidget);
    expect(find.text('Pruebas'), findsOneWidget);
  });
}
