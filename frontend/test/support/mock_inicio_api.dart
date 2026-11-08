import 'package:cody/core/fecha/dia_cdmx.dart';
import 'package:dio/dio.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';

import 'mock_movimientos_api.dart' show rutaMovimientosPrueba;
import 'mock_tablero_api.dart' show rutaTableroPrueba;

/// Responde tablero y movimientos sobre un Dio que ya tiene el simulador de
/// sesión (`mock_sesion_api.dart`), sin tocar ese archivo.
DioAdapter instalarInicioApi(
  Dio dio, {
  String totalHoy = '0.00',
  int cobrosHoy = 0,
  List<Map<String, dynamic>> movimientos = const [],
}) {
  final ahora = ahoraCdmx();
  final hoy =
      '${ahora.year}-${ahora.month.toString().padLeft(2, '0')}-${ahora.day.toString().padLeft(2, '0')}';
  final adapter = DioAdapter(dio: dio);
  adapter.onGet(
    rutaTableroPrueba,
    (server) => server.reply(200, {
      'zona': 'America/Mexico_City',
      'confirmado': {
        'filas': cobrosHoy == 0
            ? <Object>[]
            : [
                {
                  'dia': '2026-11-08',
                  'canal': 'qr_general',
                  'concepto': 'Tacos',
                  'etiqueta': 'QR general',
                  'total': totalHoy,
                  'cantidad': cobrosHoy,
                },
              ],
        'total': totalHoy,
      },
      'desarrollo': {'filas': <Object>[], 'total': '0.00'},
    }),
    queryParameters: {'desde': hoy, 'hasta': hoy},
  );
  adapter.onGet(
    rutaMovimientosPrueba,
    (server) => server.reply(200, movimientos),
  );
  return adapter;
}
