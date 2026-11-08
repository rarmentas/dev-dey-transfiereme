import 'package:dio/dio.dart';

import 'sesion_repository.dart';

class RegistroOlvidoRepository {
  RegistroOlvidoRepository(this._dio);

  final Dio _dio;

  Future<String> solicitarAlta({
    required String correo,
    required String contrasena,
  }) async {
    return _detalleDesdePost(
      '/api/sesion/alta/solicitar/',
      {'correo': correo, 'contraseña': contrasena},
      exitoMinimo: 200,
    );
  }

  Future<String> confirmarAlta({
    required String correo,
    required String codigo,
  }) async {
    return _detalleDesdePost(
      '/api/sesion/alta/confirmar/',
      {'correo': correo, 'código': codigo},
      exitoMinimo: 200,
    );
  }

  Future<String> solicitarOlvido({required String correo}) async {
    return _detalleDesdePost(
      '/api/sesion/olvido/solicitar/',
      {'correo': correo},
      exitoMinimo: 200,
    );
  }

  Future<String> restablecerOlvido({
    required String correo,
    required String codigo,
    required String contrasena,
  }) async {
    return _detalleDesdePost(
      '/api/sesion/olvido/restablecer/',
      {
        'correo': correo,
        'código': codigo,
        'contraseña': contrasena,
      },
      exitoMinimo: 200,
    );
  }

  Future<String> _detalleDesdePost(
    String ruta,
    Map<String, String> data, {
    required int exitoMinimo,
  }) async {
    final respuesta = await _dio.post<Map<String, dynamic>>(ruta, data: data);
    final status = respuesta.statusCode ?? 0;
    final detalle = respuesta.data?['detail'];
    if (status >= 200 && status < 300) {
      if (detalle is String && detalle.isNotEmpty) {
        return detalle;
      }
      return 'Listo.';
    }
    if (detalle is String && detalle.isNotEmpty) {
      throw SesionApiException(detalle);
    }
    throw SesionApiException(
      'No pudimos completar la solicitud (código $status).',
    );
  }
}
