import 'package:dio/dio.dart';

import 'venta.dart';

class VentaApiException implements Exception {
  VentaApiException(this.mensaje);

  final String mensaje;

  @override
  String toString() => mensaje;
}

class VentaPendienteException implements Exception {
  VentaPendienteException(this.movimientoId);

  final int movimientoId;
}

class CuentaNoActiveException implements Exception {
  CuentaNoActiveException(this.mensaje);

  final String mensaje;
}

class PeyException implements Exception {
  PeyException({required this.puedeHaberseCreado, required this.mensaje});

  final bool puedeHaberseCreado;
  final String mensaje;
}

class ValidacionVentaException implements Exception {
  ValidacionVentaException(this.mensaje);

  final String mensaje;
}

class VentaRepository {
  VentaRepository(this._dio);

  final Dio _dio;

  static const ruta = '/api/ventas/';

  Future<Venta> crear({
    required String monto,
    String concepto = '',
    String referencia = '',
  }) async {
    try {
      final respuesta = await _dio.post<dynamic>(
        ruta,
        data: {
          'monto': monto.trim(),
          'concepto': concepto,
          'referencia': referencia.trim(),
        },
      );
      return _leerCreacion(respuesta.statusCode ?? 0, respuesta.data);
    } on VentaPendienteException {
      rethrow;
    } on CuentaNoActiveException {
      rethrow;
    } on PeyException {
      rethrow;
    } on ValidacionVentaException {
      rethrow;
    } on VentaApiException {
      rethrow;
    } on DioException catch (error) {
      final pey = _peyDesdeDio(error);
      if (pey != null) {
        throw pey;
      }
      throw VentaApiException(_mensajeDeDio(error));
    }
  }

  Future<Venta> obtener(int movimientoId) async {
    try {
      final respuesta = await _dio.get<dynamic>('$ruta$movimientoId/');
      final status = respuesta.statusCode ?? 0;
      if (status == 200) {
        return Venta.fromJson(_mapa(respuesta.data));
      }
      throw _errorDesdeRespuesta(respuesta.data, status);
    } on VentaApiException {
      rethrow;
    } on DioException catch (error) {
      throw VentaApiException(_mensajeDeDio(error));
    } on FormatException {
      throw VentaApiException('No pudimos leer la venta. Intente de nuevo.');
    }
  }
}

Venta _leerCreacion(int status, Object? data) {
  if (status == 201) {
    return Venta.fromJson(_mapa(data));
  }
  if (status == 409) {
    final mapa = data is Map ? data : const <String, dynamic>{};
    final id = mapa['movimiento_id'];
    if (id is int) {
      throw VentaPendienteException(id);
    }
    final detalle = _detalle(data);
    throw CuentaNoActiveException(detalle ?? 'La cuenta no está ACTIVE.');
  }
  if (status == 400) {
    throw ValidacionVentaException(_mensajeValidacion(data));
  }
  if (status == 502) {
    throw _pey(data);
  }
  throw _errorDesdeRespuesta(data, status);
}

PeyException? _peyDesdeDio(DioException error) {
  if (error.response?.statusCode == 502) {
    return _pey(error.response?.data);
  }
  return null;
}

PeyException _pey(Object? data) {
  final mapa = data is Map ? data : const <String, dynamic>{};
  return PeyException(
    puedeHaberseCreado: mapa['puede_haberse_creado'] == true,
    mensaje: _detalle(data) ?? 'pey no pudo crear el cobro.',
  );
}

String _mensajeValidacion(Object? data) {
  if (data is! Map) {
    return 'Revise los datos de la venta.';
  }
  final partes = <String>[];
  for (final valor in data.values) {
    if (valor is List) {
      for (final item in valor) {
        if (item is String && item.isNotEmpty) {
          partes.add(item);
        }
      }
    } else if (valor is String && valor.isNotEmpty) {
      partes.add(valor);
    }
  }
  if (partes.isEmpty) {
    return 'Revise los datos de la venta.';
  }
  return partes.join('\n');
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

VentaApiException _errorDesdeRespuesta(Object? data, int status) {
  final detalle = _detalle(data);
  if (detalle != null) {
    return VentaApiException(detalle);
  }
  if (status >= 500) {
    return VentaApiException(_mensajeServidor);
  }
  return VentaApiException('No pudimos completar la venta (código $status).');
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
      return 'No pudimos completar la venta. Intente de nuevo.';
    default:
      return 'No pudimos completar la venta. Intente de nuevo.';
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
