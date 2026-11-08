import 'package:dio/dio.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';

Dio crearDioVenta({String baseUrl = 'http://test'}) {
  return Dio(
    BaseOptions(
      baseUrl: baseUrl,
      headers: const {'Accept': 'application/json'},
      validateStatus: (status) => status != null && status < 500,
    ),
  );
}

const rutaCrearVenta = '/api/ventas/';

class PeticionVenta {
  PeticionVenta(this.method, this.path);

  final String method;
  final String path;
}

class MockVentaApi {
  MockVentaApi(this.dio) : adapter = DioAdapter(dio: dio) {
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          peticiones.add(PeticionVenta(options.method, options.path));
          handler.next(options);
        },
      ),
    );
  }

  final Dio dio;
  final DioAdapter adapter;
  final List<PeticionVenta> peticiones = [];

  int get lecturas =>
      peticiones.where((peticion) => peticion.method == 'GET').length;

  void alCrear(int status, Map<String, dynamic> cuerpo) {
    adapter.onPost(
      rutaCrearVenta,
      (server) => server.reply(status, cuerpo),
      data: Matchers.any,
    );
  }

  void alObtener(List<Map<String, dynamic>> estados) {
    var indice = 0;
    adapter.onGet(
      RegExp(r'/api/ventas/\d+/?'),
      (server) => server.replyCallback(200, (_) {
        final actual = indice < estados.length ? indice : estados.length - 1;
        indice += 1;
        return estados[actual];
      }),
    );
  }
}

Map<String, dynamic> cuerpoVenta({
  required int id,
  required String estado,
  String monto = '12.50',
  String concepto = 'Tacos',
  String? venceEn,
  String? pagadoEn,
  String qrString = 'QR-VENTA-DEMO',
  String canal = 'qr_venta',
}) {
  return {
    'movimiento_id': id,
    'canal': canal,
    'estado': estado,
    'monto': monto,
    'concepto': concepto,
    'vence_en': venceEn,
    'pagado_en': pagadoEn,
    'qr_string': qrString,
  };
}

const rutaCrearNotificacion = '/api/ventas/notificacion/';

extension MockVentaNotificacion on MockVentaApi {
  void alCrearNotificacion(int status, Map<String, dynamic> cuerpo) {
    adapter.onPost(
      rutaCrearNotificacion,
      (server) => server.reply(status, cuerpo),
      data: Matchers.any,
    );
  }
}

Map<String, dynamic> cuerpoNotificacion({
  required int id,
  String monto = '120.00',
  String concepto = 'Transferencia',
  String? venceEn,
  String telefonoFinal = '4321',
}) {
  return {
    'movimiento_id': id,
    'cobro_id': 70,
    'canal': 'notificacion',
    'monto': monto,
    'concepto': concepto,
    'estado': 'pendiente',
    'vence_en': venceEn,
    'origen': 'app',
    'telefono_final': telefonoFinal,
  };
}
