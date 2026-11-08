import 'package:dio/dio.dart';

class ComercioApiException implements Exception {
  ComercioApiException(this.mensaje);

  final String mensaje;

  @override
  String toString() => mensaje;
}

class ComercioActualizado {
  const ComercioActualizado({required this.id, required this.nombre});

  final int id;
  final String nombre;
}

class ComercioRepository {
  ComercioRepository(this._dio);

  final Dio _dio;

  static const ruta = '/api/cuenta/comercio/';

  Future<ComercioActualizado> actualizarNombre(String nombre) async {
    try {
      final respuesta = await _dio.patch<dynamic>(
        ruta,
        data: {'nombre': nombre.trim()},
      );
      final status = respuesta.statusCode ?? 0;
      if (status == 200) {
        final mapa = _mapa(respuesta.data);
        final id = mapa['id'];
        final guardado = mapa['nombre'];
        if (id is int && guardado is String && guardado.isNotEmpty) {
          return ComercioActualizado(id: id, nombre: guardado);
        }
        throw const FormatException('respuesta');
      }
      throw _errorDesdeRespuesta(respuesta.data, status);
    } on ComercioApiException {
      rethrow;
    } on DioException catch (error) {
      throw ComercioApiException(_mensajeDeDio(error));
    } on FormatException {
      throw ComercioApiException(
        'No pudimos leer la respuesta. Inténtalo de nuevo.',
      );
    }
  }
}

const _mensajeServidor =
    'El servidor no está disponible en este momento. Inténtalo de nuevo más tarde.';

Map<String, dynamic> _mapa(Object? valor) {
  if (valor is Map<String, dynamic>) {
    return valor;
  }
  if (valor is Map) {
    return Map<String, dynamic>.from(valor);
  }
  throw const FormatException('respuesta');
}

ComercioApiException _errorDesdeRespuesta(Object? data, int status) {
  final detalle = _detalle(data);
  if (detalle != null) {
    return ComercioApiException(detalle);
  }
  if (status >= 500) {
    return ComercioApiException(_mensajeServidor);
  }
  return ComercioApiException('No pudimos guardar el nombre (código $status).');
}

String _mensajeDeDio(DioException error) {
  final detalle = _detalle(error.response?.data);
  if (detalle != null) {
    return detalle;
  }
  switch (error.type) {
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.sendTimeout:
    case DioExceptionType.receiveTimeout:
      return 'La solicitud tardó demasiado. Verifica tu conexión e inténtalo de nuevo.';
    case DioExceptionType.connectionError:
      return 'No pudimos conectar con el servidor. Verifica tu conexión e inténtalo de nuevo.';
    case DioExceptionType.badResponse:
      final codigo = error.response?.statusCode;
      if (codigo != null && codigo >= 500) {
        return _mensajeServidor;
      }
      return 'No pudimos guardar el nombre. Inténtalo de nuevo.';
    default:
      return 'No pudimos guardar el nombre. Inténtalo de nuevo.';
  }
}

String? _detalle(Object? data) {
  if (data is Map) {
    final detalle = data['detail'];
    if (detalle is String && detalle.isNotEmpty) {
      return detalle;
    }
  }
  return null;
}
