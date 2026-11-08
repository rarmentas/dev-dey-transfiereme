import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';

Map<String, dynamic> fixtureTablero() {
  final texto = File('test/fixtures/tablero.json').readAsStringSync();
  return jsonDecode(texto) as Map<String, dynamic>;
}

Dio crearDioTablero({String baseUrl = 'http://test'}) {
  return Dio(
    BaseOptions(
      baseUrl: baseUrl,
      headers: const {'Accept': 'application/json'},
      validateStatus: (status) => status != null && status < 500,
    ),
  );
}

const rutaTableroPrueba = '/api/movimientos/tablero/';

class PeticionTablero {
  PeticionTablero(this.method, this.path, this.queryParameters);

  final String method;
  final String path;
  final Map<String, dynamic> queryParameters;
}

class MockTableroApi {
  MockTableroApi(this.dio) : adapter = DioAdapter(dio: dio) {
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          peticiones.add(
            PeticionTablero(
              options.method,
              options.path,
              Map<String, dynamic>.from(options.queryParameters),
            ),
          );
          handler.next(options);
        },
      ),
    );
  }

  final Dio dio;
  final DioAdapter adapter;
  final List<PeticionTablero> peticiones = [];

  void responder(Map<String, dynamic> cuerpo) {
    adapter.reset();
    adapter.onGet(rutaTableroPrueba, (server) => server.reply(200, cuerpo));
  }

  void responderFixture() {
    responder(fixtureTablero());
  }

  void responderVacio() {
    responder(const {
      'zona': 'America/Mexico_City',
      'confirmado': {'filas': <Object>[], 'total': '0.00'},
      'desarrollo': {'filas': <Object>[], 'total': '0.00'},
    });
  }

  void responderError(int status) {
    adapter.reset();
    adapter.onGet(
      rutaTableroPrueba,
      (server) => server.reply(status, <String, dynamic>{}),
    );
  }
}
