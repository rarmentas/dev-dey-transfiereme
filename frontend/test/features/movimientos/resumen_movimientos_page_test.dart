import 'package:cody/features/movimientos/data/movimientos_repository.dart';
import 'package:cody/features/movimientos/presentation/movimientos_providers.dart';
import 'package:cody/features/movimientos/presentation/resumen_movimientos_page.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/mock_movimientos_api.dart';

Future<void> _montar(
  WidgetTester tester,
  MockMovimientosApi mock, {
  bool semana = true,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        movimientosRepositoryProvider.overrideWith(
          (ref) => MovimientosRepository(mock.dio),
        ),
        movimientosAhoraProvider.overrideWithValue(DateTime(2026, 11, 7, 20)),
      ],
      child: MaterialApp(
        theme: TfTheme.light,
        home: const ResumenMovimientosPage(),
      ),
    ),
  );
  await _esperar(tester);
  if (semana) await _verSemana(tester);
}

Future<void> _verSemana(WidgetTester tester) async {
  await tester.tap(find.text('Semana'));
  await tester.pump();
}

/// Riverpod 3 agenda el trabajo del provider en un temporizador de duración
/// cero. `pump` sin duración no lo dispara.
Future<void> _esperar(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 1));
  await tester.pump();
}

void main() {
  test('el mock responde el listado', () async {
    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.responderLista(fixtureTresCanales());
    final lista = await MovimientosRepository(mock.dio).listar();
    expect(lista, hasLength(3));
    expect(lista.first.conceptoVisible, 'Tacos al pastor');
  });

  testWidgets('lista los tres canales con monto exacto', (tester) async {
    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.responderLista(fixtureTresCanales());

    await _montar(tester, mock);

    expect(find.text('Movimientos'), findsOneWidget);
    expect(find.text('Tacos al pastor'), findsOneWidget);
    expect(find.text('Refresco'), findsOneWidget);
    expect(find.text('Agua natural'), findsOneWidget);
    expect(find.textContaining('QR general'), findsOneWidget);
    expect(find.textContaining('QR de venta'), findsOneWidget);
    expect(find.textContaining('Notificación'), findsOneWidget);
    // 3 montos + el total del día pagado.
    expect(find.text(r'$0.01'), findsNWidgets(4));
    expect(find.text('Pagado'), findsOneWidget);
    expect(find.text('Pendiente'), findsOneWidget);
    expect(find.text('Vencido'), findsOneWidget);
    expect(find.text('Prueba'), findsOneWidget);
    expect(find.byType(RefreshIndicator), findsOneWidget);
  });

  testWidgets('lista vacía muestra el texto de vacío', (tester) async {
    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.responderVacio();

    await _montar(tester, mock, semana: false);

    expect(find.text('Aún no tienes cobros'), findsOneWidget);
    expect(find.text('Cobra y aquí verás cada pago.'), findsOneWidget);
    expect(find.text('Prueba'), findsNothing);
  });

  testWidgets('error 500 muestra mensaje y Reintentar vuelve a pedir', (
    tester,
  ) async {
    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.responderError(500);

    await _montar(tester, mock, semana: false);

    expect(
      find.text(
        'El servidor no está disponible en este momento. Intenta de nuevo más tarde.',
      ),
      findsOneWidget,
    );
    expect(find.text('Reintentar'), findsOneWidget);
    expect(mock.llamadas, 1);

    mock.responderLista(fixtureTresCanales());
    await tester.tap(find.text('Reintentar'));
    await _esperar(tester);
    await _verSemana(tester);

    expect(mock.llamadas, 2);
    expect(find.text('Tacos al pastor'), findsOneWidget);
    expect(find.text('Refresco'), findsOneWidget);
    expect(find.text('Agua natural'), findsOneWidget);
    expect(find.text('Prueba'), findsOneWidget);
  });

  testWidgets('el filtro Hoy/Semana/Mes filtra por fecha local', (
    tester,
  ) async {
    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.responderLista(fixtureTresCanales());

    await _montar(tester, mock);
    await tester.tap(find.text('Hoy'));
    await tester.pump();

    expect(find.text('Tacos al pastor'), findsOneWidget);
    expect(find.text('Refresco'), findsNothing);
    expect(find.textContaining('HOY · 1 COBRO'), findsOneWidget);
    expect(find.text(r'$0.01'), findsNWidgets(2));

    await tester.tap(find.text('Mes'));
    await tester.pump();
    expect(find.text('Agua natural'), findsOneWidget);
    expect(find.textContaining('VIE 06 NOV · 1 COBRO'), findsOneWidget);
  });

  testWidgets('el chip Prueba solo aparece en origen_desarrollo', (
    tester,
  ) async {
    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.responderLista(fixtureTresCanales());

    await _montar(tester, mock);

    expect(find.text('Prueba'), findsOneWidget);
    expect(find.byType(Chip), findsOneWidget);

    final chip = tester.widget<Chip>(find.byType(Chip));
    final etiqueta = chip.label;
    expect(etiqueta, isA<Text>());
    expect((etiqueta as Text).data, 'Prueba');

    final tarjetaPrueba = find.ancestor(
      of: find.text('Prueba'),
      matching: find.byType(Card),
    );
    expect(
      find.descendant(of: tarjetaPrueba, matching: find.text('Refresco')),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: tarjetaPrueba,
        matching: find.text('Tacos al pastor'),
      ),
      findsNothing,
    );
    expect(
      find.descendant(of: tarjetaPrueba, matching: find.text('Agua natural')),
      findsNothing,
    );
  });
}
