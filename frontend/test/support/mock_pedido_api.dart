import 'package:dio/dio.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';

Dio crearDioPedido() => Dio(
  BaseOptions(
    baseUrl: 'http://test',
    validateStatus: (s) => s != null && s < 500,
  ),
);

class PeticionPedido {
  PeticionPedido(this.metodo, this.path, this.cuerpo);
  final String metodo;
  final String path;
  final dynamic cuerpo;
}

class MockPedidoApi {
  MockPedidoApi(this.dio) : adapter = DioAdapter(dio: dio) {
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (opciones, handler) {
          peticiones.add(
            PeticionPedido(opciones.method, opciones.path, opciones.data),
          );
          handler.next(opciones);
        },
      ),
    );
  }
  final Dio dio;
  final DioAdapter adapter;
  final List<PeticionPedido> peticiones = [];
  void responder(
    String metodo,
    String path,
    int status,
    Map<String, dynamic> cuerpo,
  ) {
    if (metodo == 'GET') adapter.onGet(path, (s) => s.reply(status, cuerpo));
    if (metodo == 'PUT') {
      adapter.onPut(path, (s) => s.reply(status, cuerpo), data: Matchers.any);
    }
    if (metodo == 'POST') {
      adapter.onPost(path, (s) => s.reply(status, cuerpo), data: Matchers.any);
    }
  }
}

Map<String, dynamic> pedidoJson({
  bool cotizado = false,
  bool aceptado = false,
  int version = 1,
}) => {
  'id': 'abc',
  'numero': 7,
  'version': version,
  'estado': aceptado ? 'aceptado' : 'en_revision',
  'cliente_etiqueta': '1234',
  'renglones': [
    {
      'renglon_id': 'r1',
      'texto_solicitado': 'Leche',
      'cantidad_solicitada': null,
      'unidad_solicitada': null,
      'descripcion': 'Leche',
      'cantidad': '1',
      'unidad': 'pieza',
      'precio_unitario_centavos': 1250,
      'resolucion': 'incluido',
      'motivo_exclusion': '',
      'subtotal_centavos': 1250,
    },
  ],
  'cotizacion': cotizado
      ? {
          'revision': 2,
          'total_comercial_centavos': 1250,
          'importe_efectivo_centavos': 1,
          'demo_mode': true,
          'token_resumen': 'P7-R2',
        }
      : null,
  'aceptacion': aceptado ? {'id': 'a'} : null,
};
Map<String, dynamic> exito(dynamic data) => {'ok': true, 'data': data};
