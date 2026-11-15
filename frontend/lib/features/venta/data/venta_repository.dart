import 'package:dio/dio.dart';

import 'venta.dart';
import '../../pedidos/data/clave_comando.dart';

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
  ValidacionVentaException(this.mensaje, {this.campo});

  final String mensaje;
  final String? campo;
}

class VentaRepository {
  VentaRepository(this._dio);

  final Dio _dio;
  final ClaveComando _clave = ClaveComando();

  static const ruta = '/api/ventas/';

  static const rutaNotificacion = '/api/ventas/notificacion/';

  Future<Venta> crear({
    required String monto,
    String concepto = '',
    String referencia = '',
  }) {
    return _crearEn(ruta, {
      'monto': monto.trim(),
      'concepto': concepto,
      'referencia': referencia.trim(),
    });
  }

  /// Cobro enviado al celular del cliente (10 dígitos, sin lada +52).
  Future<Venta> crearNotificacion({
    required String monto,
    required String telefono,
    String concepto = '',
    String referencia = '',
  }) {
    return _crearEn(rutaNotificacion, {
      'monto': monto.trim(),
      'telefono': telefono.trim(),
      'concepto': concepto,
      'referencia': referencia.trim(),
    });
  }

  Future<Venta> _crearEn(String destino, Map<String, dynamic> datos) async {
    try {
      final respuesta = await _dio.post<dynamic>(
        destino,
        data: datos,
        options: Options(
          headers: {
            'Idempotency-Key': _clave.para({'ruta': destino, ...datos}),
          },
        ),
      );
      final venta = _leerCreacion(respuesta.statusCode ?? 0, respuesta.data);
      _clave.limpiar();
      return venta;
    } on VentaPendienteException {
      _clave.limpiar();
      rethrow;
    } on CuentaNoActiveException {
      _clave.limpiar();
      rethrow;
    } on PeyException catch (e) {
      if (!e.puedeHaberseCreado) _clave.limpiar();
      rethrow;
    } on ValidacionVentaException {
      _clave.limpiar();
      rethrow;
    } on VentaApiException {
      _clave.limpiar();
      rethrow;
    } on DioException catch (error) {
      final response = error.response;
      if (response != null) {
        try {
          return _leerCreacion(response.statusCode ?? 0, response.data);
        } on PeyException catch (e) {
          if (!e.puedeHaberseCreado) _clave.limpiar();
          rethrow;
        } catch (_) {
          if ((response.statusCode ?? 0) < 500) _clave.limpiar();
          rethrow;
        }
      }
      throw PeyException(
        puedeHaberseCreado: true,
        mensaje: 'No sabemos si se generó el cobro; no lo repitas.',
      );
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
      throw VentaApiException('No pudimos leer el cobro. Intenta de nuevo.');
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
    final codigo = mapa['codigo'];
    if (codigo == 'CUENTA_NO_ACTIVE' ||
        (codigo == null &&
            !mapa.containsKey('movimiento_id') &&
            mapa['detail'] == 'La cuenta no está ACTIVE.')) {
      throw CuentaNoActiveException('La cuenta no está activa.');
    }
    if (codigo == 'COBRO_EN_CURSO' || codigo == 'COBRO_INCIERTO') {
      throw VentaApiException(
        'Hay un cobro en curso o sin confirmar; no lo repitas.',
      );
    }
    throw VentaApiException('No pudimos completar el cobro. Intenta de nuevo.');
  }
  if (status == 400) {
    throw ValidacionVentaException(
      _mensajeValidacion(data),
      campo: data is Map && data.containsKey('monto') ? 'monto' : null,
    );
  }
  if (status == 502) {
    throw _pey(data);
  }
  if (status == 401 || (data is Map && data['codigo'] == 'SESION_TERMINADA')) {
    throw VentaApiException('Tu sesión terminó. Vuelve a entrar.');
  }
  if (status == 403 &&
      data is Map &&
      data['codigo'] == 'RUTA_BLOQUEADA_EN_DEMO') {
    throw VentaApiException('Este cobro no está disponible en demo.');
  }
  if (status >= 500) {
    throw PeyException(
      puedeHaberseCreado: true,
      mensaje: 'No sabemos si se generó el cobro; no lo repitas.',
    );
  }
  throw _errorDesdeRespuesta(data, status);
}

PeyException _pey(Object? data) {
  final mapa = data is Map ? data : const <String, dynamic>{};
  return PeyException(
    puedeHaberseCreado: mapa['puede_haberse_creado'] != false,
    mensaje: _detalle(data) ?? 'pey no pudo crear el cobro.',
  );
}

String _mensajeValidacion(Object? data) {
  if (data is! Map) {
    return 'Revisa los datos del cobro.';
  }
  final partes = <String>[];
  for (final entrada in data.entries) {
    if (entrada.key == 'codigo') continue;
    final valor = entrada.value;
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
    return 'Revisa los datos del cobro.';
  }
  return partes.join('\n');
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

VentaApiException _errorDesdeRespuesta(Object? data, int status) {
  final detalle = _detalle(data);
  if (detalle != null) {
    return VentaApiException(detalle);
  }
  if (status >= 500) {
    return VentaApiException(_mensajeServidor);
  }
  return VentaApiException('No pudimos completar el cobro (código $status).');
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
      return 'La solicitud tardó demasiado. Revisa tu conexión e intenta de nuevo.';
    case DioExceptionType.connectionError:
      return 'No pudimos conectar con el servidor. Revisa tu conexión e intenta de nuevo.';
    case DioExceptionType.badResponse:
      final codigo = error.response?.statusCode;
      if (codigo != null && codigo >= 500) {
        return _mensajeServidor;
      }
      return 'No pudimos completar el cobro. Intenta de nuevo.';
    default:
      return 'No pudimos completar el cobro. Intenta de nuevo.';
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
