import 'package:dio/dio.dart';

class QrGeneralApiException implements Exception {
  QrGeneralApiException(this.mensaje);

  final String mensaje;

  @override
  String toString() => mensaje;
}

/// Resultado de pedir el QR general del comercio.
class QrGeneralResultado {
  const QrGeneralResultado.activo(String this.qrString) : cuentaNoActiva = false;

  const QrGeneralResultado.cuentaNoActiva()
      : qrString = null,
        cuentaNoActiva = true;

  final String? qrString;
  final bool cuentaNoActiva;
}

class QrGeneralRepository {
  QrGeneralRepository(this._dio);

  final Dio _dio;

  static const ruta = '/api/cobro/qr-general/';

  /// `POST /api/cobro/qr-general/` con cuerpo `{}`.
  /// 200/201 devuelve `qr_string`; 400 con `tipo: INVALID_STATE` es cuenta no activa.
  Future<QrGeneralResultado> obtener() async {
    try {
      final respuesta = await _dio.post<dynamic>(ruta, data: <String, dynamic>{});
      final status = respuesta.statusCode ?? 0;
      final data = respuesta.data;
      if (status == 200 || status == 201) {
        if (data is Map) {
          final qr = data['qr_string'];
          if (qr is String && qr.trim().isNotEmpty) {
            return QrGeneralResultado.activo(qr);
          }
        }
        throw QrGeneralApiException(
          'No pudimos leer tu código de cobro. Inténtalo de nuevo.',
        );
      }
      if (status == 400 && data is Map && data['tipo'] == 'INVALID_STATE') {
        return const QrGeneralResultado.cuentaNoActiva();
      }
      throw QrGeneralApiException(_mensajeDe(data, status));
    } on QrGeneralApiException {
      rethrow;
    } on DioException catch (error) {
      final data = error.response?.data;
      if (error.response?.statusCode == 400 &&
          data is Map &&
          data['tipo'] == 'INVALID_STATE') {
        return const QrGeneralResultado.cuentaNoActiva();
      }
      throw QrGeneralApiException(_mensajeDeDio(error));
    }
  }
}

const _mensajeServidor =
    'El servidor no está disponible en este momento. Inténtalo más tarde.';

String _mensajeDe(Object? data, int status) {
  if (data is Map) {
    final detalle = data['detail'];
    if (detalle is String && detalle.isNotEmpty) {
      return detalle;
    }
  }
  if (status >= 500) {
    return _mensajeServidor;
  }
  return 'No pudimos cargar tu código de cobro (código $status).';
}

String _mensajeDeDio(DioException error) {
  switch (error.type) {
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.sendTimeout:
    case DioExceptionType.receiveTimeout:
      return 'La solicitud tardó demasiado. Verifica tu conexión e inténtalo de nuevo.';
    case DioExceptionType.connectionError:
      return 'No pudimos conectar con el servidor. Verifica tu conexión e inténtalo de nuevo.';
    default:
      final codigo = error.response?.statusCode;
      if (codigo != null && codigo >= 500) {
        return _mensajeServidor;
      }
      return 'No pudimos cargar tu código de cobro. Inténtalo de nuevo.';
  }
}
