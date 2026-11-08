import 'package:cody/features/movimientos/data/movimientos_repository.dart';
import 'package:cody/features/movimientos/presentation/movimientos_providers.dart';
import 'package:cody/features/movimientos/presentation/resumen_movimientos_page.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/mock_movimientos_api.dart';

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
  testWidgets('ningún movimiento ofrece renombrar el concepto', (
    tester,
  ) async {
    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.responderLista(fixtureTresCanales());

    await _montar(tester, mock);

    expect(find.byTooltip('Renombrar'), findsNothing);
    expect(find.byIcon(Icons.edit_rounded), findsNothing);
    expect(find.byType(AlertDialog), findsNothing);
    expect(mock.parches, isEmpty);
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
