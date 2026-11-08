import 'package:cody/features/movimientos/data/movimientos_repository.dart';
import 'package:cody/features/movimientos/presentation/movimientos_providers.dart';
import 'package:cody/features/movimientos/presentation/resumen_movimientos_page.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/mock_movimientos_api.dart';

const _mensaje409 = 'Solo se puede renombrar un movimiento cobrado.';

Map<String, dynamic> _movimiento({
  required int id,
  required String visible,
  required String concepto,
  required String estado,
}) {
  return {
    'id': id,
    'monto': '0.01',
    'concepto': concepto,
    'concepto_visible': visible,
    'canal': 'qr_venta',
    'estado': estado,
    'origen': 'origen_desarrollo',
    'creado_en': '2026-11-07T18:00:00Z',
    'pagado_en': estado == 'pagado' ? '2026-11-07T18:05:00Z' : null,
  };
}

Future<void> _montar(WidgetTester tester, MockMovimientosApi mock) async {
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
  await tester.tap(find.text('Semana'));
  await tester.pump();
}

Future<void> _esperar(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 1));
  await tester.pump();
}

void main() {
  testWidgets('renombrar un pagado hace PATCH y recarga el nombre', (
    tester,
  ) async {
    final antes = [
      _movimiento(
        id: 1,
        visible: 'Transferencia',
        concepto: 'Transferencia',
        estado: 'pagado',
      ),
    ];
    final despues = [
      _movimiento(
        id: 1,
        visible: 'Tortas',
        concepto: 'Transferencia',
        estado: 'pagado',
      ),
    ];
    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.prepararRenombre(
      antes: antes,
      despues: despues,
      id: 1,
      dataEsperada: {'concepto_visible': 'Tortas'},
    );

    await _montar(tester, mock);
    expect(find.text('Enviado: Transferencia'), findsNothing);

    await tester.tap(find.byTooltip('Renombrar'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('Guardar'), findsOneWidget);
    await tester.enterText(find.byType(TextField), 'Tortas');
    await tester.tap(find.text('Guardar'));
    await _esperar(tester);
    await tester.pump(const Duration(milliseconds: 400));

    expect(mock.parches, hasLength(1));
    expect(mock.parches.single.path, '/api/movimientos/1/');
    expect(mock.parches.single.data, {'concepto_visible': 'Tortas'});
    expect(find.text('Tortas'), findsOneWidget);
    expect(find.text('Enviado: Transferencia'), findsOneWidget);
    expect(find.text('Transferencia'), findsNothing);
    expect(mock.llamadas, greaterThan(1));
  });

  testWidgets('un pendiente no tiene acción de renombrar', (tester) async {
    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.responderLista(fixtureTresCanales());

    await _montar(tester, mock);

    expect(find.byTooltip('Renombrar'), findsOneWidget);
    final pendiente = find.ancestor(
      of: find.text('Refresco'),
      matching: find.byType(Card),
    );
    final vencido = find.ancestor(
      of: find.text('Agua natural'),
      matching: find.byType(Card),
    );
    expect(
      find.descendant(of: pendiente, matching: find.byTooltip('Renombrar')),
      findsNothing,
    );
    expect(
      find.descendant(of: vencido, matching: find.byTooltip('Renombrar')),
      findsNothing,
    );
  });

  testWidgets('un 409 muestra el mensaje en un SnackBar', (tester) async {
    final lista = [
      _movimiento(
        id: 4,
        visible: 'Transferencia',
        concepto: 'Transferencia',
        estado: 'pagado',
      ),
    ];
    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.prepararRenombre(
      antes: lista,
      despues: lista,
      id: 4,
      statusPatch: 409,
      cuerpoPatch: {'detail': _mensaje409},
      dataEsperada: {'concepto_visible': 'Tortas'},
    );

    await _montar(tester, mock);
    await tester.tap(find.byTooltip('Renombrar'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.enterText(find.byType(TextField), 'Tortas');
    await tester.tap(find.text('Guardar'));
    await _esperar(tester);
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.text(_mensaje409), findsOneWidget);
    expect(find.text('Transferencia'), findsWidgets);
    expect(find.text('Tortas'), findsNothing);
    expect(mock.parches.single.data, {'concepto_visible': 'Tortas'});
  });

  testWidgets('muestra Enviado cuando el visible difiere del enviado', (
    tester,
  ) async {
    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.responderLista([
      _movimiento(
        id: 9,
        visible: 'Tortas',
        concepto: 'Transferencia',
        estado: 'pagado',
      ),
    ]);

    await _montar(tester, mock);

    expect(find.text('Tortas'), findsOneWidget);
    expect(find.text('Enviado: Transferencia'), findsOneWidget);
  });
}
