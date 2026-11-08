import 'package:dio/dio.dart';

import 'sesion_models.dart';

class SesionApiException implements Exception {
  SesionApiException(this.mensaje);

  final String mensaje;

  @override
  String toString() => mensaje;
}

class SesionRepository {
  SesionRepository(this._dio);

  final Dio _dio;

  static const _rutaEntrar = '/api/sesion/entrar/';
  static const _rutaEstado = '/api/sesion/estado/';
  static const _rutaSalir = '/api/sesion/salir/';

  Future<void> entrar({
    required String correo,
    required String contrasena,
  }) async {
    final respuesta = await _dio.post<Map<String, dynamic>>(
      _rutaEntrar,
      data: {'correo': correo, 'contraseña': contrasena},
    );
    final status = respuesta.statusCode ?? 0;
    if (status == 200) {
      return;
    }
    throw _errorDesdeRespuesta(respuesta.data, status);
  }

  Future<EstadoSesion?> cargarEstado() async {
    final respuesta = await _dio.get<Map<String, dynamic>>(_rutaEstado);
    final status = respuesta.statusCode ?? 0;
    if (status == 200) {
      final data = respuesta.data;
      if (data == null) {
        return null;
      }
      return EstadoSesion.fromJson(data);
    }
    if (status == 403) {
      return null;
    }
    throw _errorDesdeRespuesta(respuesta.data, status);
  }

  Future<void> salir() async {
    final respuesta = await _dio.post<Map<String, dynamic>>(_rutaSalir);
    final status = respuesta.statusCode ?? 0;
    if (status == 200) {
      return;
    }
    throw _errorDesdeRespuesta(respuesta.data, status);
  }

  SesionApiException _errorDesdeRespuesta(
    Map<String, dynamic>? data,
    int status,
  ) {
    final detalle = data?['detail'];
    if (detalle is String && detalle.isNotEmpty) {
      return SesionApiException(detalle);
    }
    return SesionApiException(
      'No pudimos completar la solicitud (código $status).',
    );
  }
}
