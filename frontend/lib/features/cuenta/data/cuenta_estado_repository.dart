import 'package:dio/dio.dart';

import 'cuenta_estado.dart';

class CuentaEstadoRepository {
  CuentaEstadoRepository(this._dio);

  final Dio _dio;

  static const rutaEstado = '/api/cuenta/pey/estado/';
  static const rutaRegistro = '/api/cuenta/pey/registro/';
  static const rutaSincronizar = '/api/cuenta/pey/sincronizar/';

  Future<EstadoCuentaPey> obtenerEstado() async {
    try {
      final respuesta = await _dio.get<dynamic>(rutaEstado);
      return _estadoDesdeRespuesta(respuesta);
    } on DioException catch (error) {
      throw cuentaPeyErrorDeDio(error);
    }
  }

  Future<EstadoCuentaPey> registrarEnPey({
    required String nombre,
    required String entidad,
    String alias = '',
    bool reemplazar = false,
  }) async {
    try {
      final respuesta = await _dio.post<dynamic>(
        rutaRegistro,
        data: {
          'nombre': nombre.trim(),
          'entidad': entidad,
          if (alias.trim().isNotEmpty) 'alias': alias.trim(),
          'reemplazar': reemplazar,
        },
      );
      return _estadoDesdeRespuesta(respuesta);
    } on DioException catch (error) {
      throw cuentaPeyErrorDeDio(error);
    }
  }

  Future<EstadoCuentaPey> sincronizar() async {
    try {
      final respuesta = await _dio.post<dynamic>(rutaSincronizar);
      return _estadoDesdeRespuesta(respuesta);
    } on DioException catch (error) {
      throw cuentaPeyErrorDeDio(error);
    }
  }

  EstadoCuentaPey _estadoDesdeRespuesta(Response<dynamic> respuesta) {
    final status = respuesta.statusCode ?? 0;
    if (status == 200) {
      return EstadoCuentaPey.fromJson(_mapa(respuesta.data));
    }
    throw _errorDesdeRespuesta(respuesta.data, status);
  }

  CuentaPeyApiException _errorDesdeRespuesta(Object? data, int status) {
    final mapa = data is Map ? Map<String, dynamic>.from(data) : null;
    final detalle = mapa?['detail'];
    final codigo = mapa?['codigo'];
    final mensaje = detalle is String && detalle.isNotEmpty
        ? detalle
        : _mensajePorStatus(status);
    if (status == 429 && mapa?['reintento_en_segundos'] is int) {
      return CuentaPeyApiException(
        '$mensaje (${mapa!['reintento_en_segundos']} s)',
        codigo: 'SYNC_PRONTO',
      );
    }
    return CuentaPeyApiException(
      mensaje,
      codigo: codigo is String ? codigo : null,
    );
  }

  String _mensajePorStatus(int status) {
    if (status == 409) {
      return 'Este comercio ya tiene cuenta en pey.';
    }
    if (status >= 500) {
      return 'El servidor no está disponible en este momento. Inténtalo de nuevo más tarde.';
    }
    return 'No pudimos completar la solicitud (código $status).';
  }
}

Map<String, dynamic> _mapa(Object? valor) {
  if (valor is Map<String, dynamic>) {
    return valor;
  }
  if (valor is Map) {
    return Map<String, dynamic>.from(valor);
  }
  throw const FormatException('respuesta');
}

CuentaPeyApiException cuentaPeyErrorDeDio(DioException error) {
  final data = error.response?.data;
  final status = error.response?.statusCode ?? 0;
  if (data is Map) {
    final detalle = data['detail'];
    final codigo = data['codigo'];
    if (detalle is String && detalle.isNotEmpty) {
      if (status == 429 && data['reintento_en_segundos'] is int) {
        return CuentaPeyApiException(
          '$detalle (${data['reintento_en_segundos']} s)',
          codigo: 'SYNC_PRONTO',
        );
      }
      return CuentaPeyApiException(
        detalle,
        codigo: codigo is String ? codigo : null,
      );
    }
  }
  return CuentaPeyApiException(
    'No pudimos comunicarnos con el servidor. Inténtalo de nuevo.',
  );
}
