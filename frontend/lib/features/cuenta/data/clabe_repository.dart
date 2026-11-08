import 'package:dio/dio.dart';

class ClabeApiException implements Exception {
  ClabeApiException(this.mensaje);

  final String mensaje;

  @override
  String toString() => mensaje;
}

class ClabeRepository {
  ClabeRepository(this._dio);

  final Dio _dio;

  static const ruta = '/api/cuenta/clabe/';

  Future<String> guardar(String clabe) async {
    try {
      final respuesta = await _dio.post<dynamic>(
        ruta,
        data: {'clabe': clabe.trim()},
      );
      final status = respuesta.statusCode ?? 0;
      if (status == 200) {
        final mapa = _mapa(respuesta.data);
        final guardada = mapa['clabe'];
        if (guardada is String && guardada.isNotEmpty) {
          return guardada;
        }
        throw const FormatException('respuesta');
      }
      throw _errorDesdeRespuesta(respuesta.data, status);
    } on ClabeApiException {
      rethrow;
    } on DioException catch (error) {
      throw ClabeApiException(_mensajeDeDio(error));
    } on FormatException {
      throw ClabeApiException('No pudimos leer la respuesta. Intente de nuevo.');
    }
  }
}

const _mensajeServidor =
    'El servidor no está disponible en este momento. Intente de nuevo más tarde.';

Map<String, dynamic> _mapa(Object? valor) {
  if (valor is Map<String, dynamic>) {
    return valor;
  }
  if (valor is Map) {
    return Map<String, dynamic>.from(valor);
  }
  throw const FormatException('respuesta');
}

ClabeApiException _errorDesdeRespuesta(Object? data, int status) {
  final detalle = _detalle(data);
  if (detalle != null) {
    return ClabeApiException(detalle);
  }
  if (status >= 500) {
    return ClabeApiException(_mensajeServidor);
  }
  return ClabeApiException('No pudimos guardar la CLABE (código $status).');
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
      return 'La solicitud tardó demasiado. Verifique su conexión e intente de nuevo.';
    case DioExceptionType.connectionError:
      return 'No pudimos conectar con el servidor. Verifique su conexión e intente de nuevo.';
    case DioExceptionType.badResponse:
      final codigo = error.response?.statusCode;
      if (codigo != null && codigo >= 500) {
        return _mensajeServidor;
      }
      return 'No pudimos guardar la CLABE. Intente de nuevo.';
    default:
      return 'No pudimos guardar la CLABE. Intente de nuevo.';
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
