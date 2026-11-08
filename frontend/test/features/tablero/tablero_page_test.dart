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
    expect(peticion.queryParameters, isEmpty);
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
    expect(mock.peticiones, hasLength(1));
    expect(find.text('Tablero'), findsOneWidget);
    expect(find.text('Cobrado'), findsOneWidget);
    expect(find.text('Pruebas'), findsOneWidget);
    expect(find.text(formatearMonto('42.50')), findsOneWidget);
    expect(find.text(formatearMonto('1.01')), findsOneWidget);
    expect(find.text(formatearMonto('43.51')), findsNothing);
    expect(find.text('07/11/2026'), findsNWidgets(2));
    expect(find.text('06/11/2026'), findsNWidgets(2));
    expect(find.text('Tortas'), findsNWidgets(2));
    expect(find.text('Transferencia'), findsOneWidget);
    expect(find.text('Refrescos'), findsOneWidget);
    expect(find.text('Prueba local'), findsNWidgets(2));
    expect(find.text('QR general'), findsNWidgets(2));
    expect(find.text('QR de venta'), findsNWidgets(2));
    expect(find.text('Notificación'), findsNWidgets(2));
    expect(find.text(formatearMonto('15.50')), findsOneWidget);
    expect(find.text(formatearMonto('0.01')), findsOneWidget);
    expect(find.text('×2'), findsOneWidget);
    expect(find.byType(RefreshIndicator), findsOneWidget);
  });

  testWidgets('tablero vacío muestra el texto de vacío', (tester) async {
    final mock = MockTableroApi(crearDioTablero());
    mock.responderVacio();

    await _montar(tester, mock);

    _soloTablero(mock);
    expect(find.text('Aún no hay cobros'), findsOneWidget);
    expect(find.text('Cobrado'), findsNothing);
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
        'El servidor no está disponible en este momento. Intente de nuevo más tarde.',
      ),
      findsOneWidget,
    );
    expect(find.text('Reintentar'), findsOneWidget);
    _soloTablero(mock);
    expect(mock.peticiones, hasLength(1));

    mock.responderFixture();
    await tester.tap(find.text('Reintentar'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 1));
    await tester.pump();

    expect(mock.peticiones, hasLength(2));
    _soloTablero(mock);
    expect(find.text('Cobrado'), findsOneWidget);
    expect(find.text(formatearMonto('42.50')), findsOneWidget);
    expect(find.text('Pruebas'), findsOneWidget);
  });
}
