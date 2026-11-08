import 'package:cody/features/movimientos/data/movimiento.dart';
import 'package:cody/features/tablero/data/tablero.dart';
import 'package:cody/features/tablero/data/tablero_repository.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/mock_tablero_api.dart';

void main() {
  test('fromJson conserva el monto y el día sin zona', () {
    final tablero = Tablero.fromJson(fixtureTablero());
    final fila = tablero.confirmado.filas.first;

    expect(tablero.zona, 'America/Mexico_City');
    expect(tablero.confirmado.total, '42.50');
    expect(tablero.confirmado.total, isA<String>());
    expect(tablero.desarrollo.total, '1.01');
    expect(fila.total, '5.00');
    expect(fila.total, isA<String>());
    expect(fila.dia, DateTime(2026, 11, 7));
    expect(fila.dia.isUtc, isFalse);
    expect(fila.diaCorto, '07/11/2026');
    expect(fila.totalFormateado, formatearMonto('5.00'));
    expect(tablero.desarrollo.filas, isNotEmpty);
  });

  test('obtener manda desde y hasta como día civil', () async {
    final mock = MockTableroApi(crearDioTablero());
    mock.responderFixture();
    final tablero = await TableroRepository(mock.dio)
        .obtener(desde: DateTime(2026, 11, 1), hasta: DateTime(2026, 11, 7));

    expect(tablero.confirmado.total, '42.50');
    expect(mock.peticiones, hasLength(1));
    expect(mock.peticiones.single.method, 'GET');
    expect(mock.peticiones.single.path, rutaTableroPrueba);
    expect(mock.peticiones.single.queryParameters['desde'], '2026-11-01');
    expect(mock.peticiones.single.queryParameters['hasta'], '2026-11-07');
  });
}
