import 'package:dio/dio.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';

/// Dio de prueba con el mismo criterio de estado que el cliente real:
/// un 500 llega como [DioException], no como respuesta exitosa.
Dio crearDioMovimientos({String baseUrl = 'http://test'}) {
  return Dio(
    BaseOptions(
      baseUrl: baseUrl,
      headers: const {'Accept': 'application/json'},
      validateStatus: (status) => status != null && status < 500,
    ),
  );
}

const rutaMovimientosPrueba = '/api/movimientos/';

List<Map<String, dynamic>> fixtureTresCanales() {
  return [
    {
      'id': 1,
      'monto': '0.01',
      'concepto_visible': 'Tacos al pastor',
      'canal': 'qr_general',
      'estado': 'pagado',
      'origen': 'origen_pey',
      'creado_en': '2026-11-07T18:00:00Z',
      'pagado_en': '2026-11-07T18:05:00Z',
    },
    {
      'id': 2,
      'monto': '0.01',
      'concepto_visible': 'Refresco',
      'canal': 'qr_venta',
      'estado': 'pendiente',
      'origen': 'origen_desarrollo',
      'creado_en': '2026-11-06T18:00:00Z',
      'pagado_en': null,
    },
    {
      'id': 3,
      'monto': '0.01',
      'concepto_visible': 'Agua natural',
      'canal': 'notificacion',
      'estado': 'vencido',
      'origen': 'origen_pey',
      'creado_en': '2026-11-05T18:00:00Z',
      'pagado_en': null,
    },
  ];
}

class MockMovimientosApi {
  MockMovimientosApi(this.dio) : adapter = DioAdapter(dio: dio) {
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          if (options.path.contains(rutaMovimientosPrueba)) {
            llamadas++;
          }
          if (options.method == 'PATCH') {
            parches.add(options);
          }
          handler.next(options);
        },
      ),
    );
  }

  final Dio dio;
  final DioAdapter adapter;
  int llamadas = 0;
  final List<RequestOptions> parches = [];

  void responderLista(List<Map<String, dynamic>> movimientos) {
    adapter.reset();
    adapter.onGet(
      rutaMovimientosPrueba,
      (server) => server.reply(200, movimientos),
    );
  }

  void responderVacio() {
    responderLista(const []);
  }

  /// El primer GET devuelve [antes]; los siguientes, [despues].
  void prepararRenombre({
    required List<Map<String, dynamic>> antes,
    required List<Map<String, dynamic>> despues,
    required int id,
    int statusPatch = 200,
    Map<String, dynamic>? cuerpoPatch,
    Map<String, dynamic>? dataEsperada,
  }) {
    adapter.reset();
    var lecturas = 0;
    adapter.onGet(rutaMovimientosPrueba, (server) {
      server.replyCallback(200, (_) {
        lecturas += 1;
        return lecturas == 1 ? antes : despues;
      });
    });
    adapter.onPatch(
      '$rutaMovimientosPrueba$id/',
      (server) => server.reply(
        statusPatch,
        cuerpoPatch ?? <String, dynamic>{},
      ),
      data: dataEsperada,
    );
  }

  void responderError(int status) {
    adapter.reset();
    adapter.onGet(
      rutaMovimientosPrueba,
      (server) => server.reply(status, <String, dynamic>{}),
    );
  }
}
