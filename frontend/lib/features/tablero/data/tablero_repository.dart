import 'package:dio/dio.dart';

import 'tablero.dart';

class TableroApiException implements Exception {
  TableroApiException(this.mensaje);

  final String mensaje;

  @override
  String toString() => mensaje;
}

class TableroRepository {
  TableroRepository(this._dio);

  final Dio _dio;

  static const ruta = '/api/movimientos/tablero/';

  Future<Tablero> obtener({DateTime? desde, DateTime? hasta}) async {
    final query = <String, String>{};
    if (desde != null) {
      query['desde'] = isoDiaTablero(desde);
    }
    if (hasta != null) {
      query['hasta'] = isoDiaTablero(hasta);
    }
    try {
      final respuesta = await _dio.get<dynamic>(
        ruta,
        queryParameters: query.isEmpty ? null : query,
      );
      final status = respuesta.statusCode ?? 0;
      if (status == 200) {
        return Tablero.fromJson(_mapa(respuesta.data));
      }
      throw _errorDesdeRespuesta(respuesta.data, status);
    } on TableroApiException {
      rethrow;
    } on DioException catch (error) {
      throw TableroApiException(_mensajeDeDio(error));
    } on FormatException {
      throw TableroApiException(
        'No pudimos leer el tablero. Intenta de nuevo.',
      );
    }
  }
}

const _mensajeServidor =
    'El servidor no está disponible en este momento. Intenta de nuevo más tarde.';

Map<String, dynamic> _mapa(Object? valor) {
  if (valor is Map<String, dynamic>) {
    return valor;
  }
  if (valor is Map) {
    return Map<String, dynamic>.from(valor);
  }
  throw const FormatException('respuesta');
}

TableroApiException _errorDesdeRespuesta(Object? data, int status) {
  final detalle = _detalle(data);
  if (detalle != null) {
    return TableroApiException(detalle);
  }
  if (status >= 500) {
    return TableroApiException(_mensajeServidor);
  }
  return TableroApiException('No pudimos cargar el tablero (código $status).');
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
      return 'La solicitud tardó demasiado. Verifica tu conexión e intenta de nuevo.';
    case DioExceptionType.connectionError:
      return 'No pudimos conectar con el servidor. Verifica tu conexión e intenta de nuevo.';
    case DioExceptionType.badResponse:
      final codigo = error.response?.statusCode;
      if (codigo != null && codigo >= 500) {
        return _mensajeServidor;
      }
      return 'No pudimos cargar el tablero. Intenta de nuevo.';
    default:
      return 'No pudimos cargar el tablero. Intenta de nuevo.';
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
