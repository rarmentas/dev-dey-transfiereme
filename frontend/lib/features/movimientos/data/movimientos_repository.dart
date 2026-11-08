import 'package:dio/dio.dart';

import 'movimiento.dart';

class MovimientosApiException implements Exception {
  MovimientosApiException(this.mensaje);

  final String mensaje;

  @override
  String toString() => mensaje;
}

class MovimientosRepository {
  MovimientosRepository(this._dio);

  final Dio _dio;

  static const rutaListado = '/api/movimientos/';

  Future<void> renombrarConcepto(int id, String nuevo) async {
    try {
      final respuesta = await _dio.patch<dynamic>(
        '$rutaListado$id/',
        data: {'concepto_visible': nuevo},
      );
      final status = respuesta.statusCode ?? 0;
      if (status == 200) {
        return;
      }
      throw _errorRenombre(respuesta.data, status);
    } on MovimientosApiException {
      rethrow;
    } on DioException catch (error) {
      throw MovimientosApiException(_mensajeDeDio(error));
    }
  }

  Future<List<Movimiento>> listar() async {
    try {
      final respuesta = await _dio.get<dynamic>(rutaListado);
      final status = respuesta.statusCode ?? 0;
      if (status == 200) {
        return _leerLista(respuesta.data);
      }
      throw _errorDesdeRespuesta(respuesta.data, status);
    } on MovimientosApiException {
      rethrow;
    } on DioException catch (error) {
      throw MovimientosApiException(_mensajeDeDio(error));
    }
  }

  List<Movimiento> _leerLista(Object? data) {
    if (data is! List) {
      throw MovimientosApiException(
        'No pudimos leer los movimientos. Intente de nuevo.',
      );
    }
    final lista = <Movimiento>[];
    for (final item in data) {
      if (item is Map<String, dynamic>) {
        lista.add(Movimiento.fromJson(item));
      } else if (item is Map) {
        lista.add(Movimiento.fromJson(Map<String, dynamic>.from(item)));
      } else {
        throw MovimientosApiException(
          'No pudimos leer los movimientos. Intente de nuevo.',
        );
      }
    }
    return lista;
  }

  MovimientosApiException _errorRenombre(Object? data, int status) {
    final detalle = _detalle(data);
    if (detalle != null) {
      return MovimientosApiException(detalle);
    }
    if (status >= 500) {
      return MovimientosApiException(_mensajeServidor);
    }
    return MovimientosApiException(
      'No pudimos renombrar el concepto. Intente de nuevo.',
    );
  }

  MovimientosApiException _errorDesdeRespuesta(Object? data, int status) {
    final detalle = _detalle(data);
    if (detalle != null) {
      return MovimientosApiException(detalle);
    }
    if (status >= 500) {
      return MovimientosApiException(_mensajeServidor);
    }
    return MovimientosApiException(
      'No pudimos cargar los movimientos (código $status).',
    );
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
        return 'No pudimos cargar los movimientos. Intente de nuevo.';
      default:
        return 'No pudimos cargar los movimientos. Intente de nuevo.';
    }
  }
}

const _mensajeServidor =
    'El servidor no está disponible en este momento. Intente de nuevo más tarde.';

String? _detalle(Object? data) {
  if (data is Map) {
    final detalle = data['detail'];
    if (detalle is String && detalle.isNotEmpty) {
      return detalle;
    }
  }
  return null;
}
