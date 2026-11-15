import 'package:dio/dio.dart';

import 'pedido.dart';

class PedidoException implements Exception {
  PedidoException(
    this.codigo,
    this.status,
    this.mensaje, {
    this.pedidoVersion,
    this.errores = const {},
  });
  final String codigo;
  final int? status;
  final String mensaje;
  final int? pedidoVersion;
  final Map<String, dynamic> errores;
  @override
  String toString() => mensaje;
}

class PedidoRepository {
  PedidoRepository(this._dio);
  final Dio _dio;
  static const ruta = '/api/pedidos/';

  Future<Map<String, dynamic>> catalogo() async =>
      _solicitar('GET', '${ruta}catalogo/');
  Future<Map<String, dynamic>> guardarProducto(
    int? id,
    Map<String, dynamic> cuerpo,
  ) async => _solicitar(
    id == null ? 'POST' : 'PUT',
    id == null ? '${ruta}catalogo/' : '${ruta}catalogo/$id/',
    cuerpo,
  );
  Future<Map<String, dynamic>> configurarAgente(bool habilitado) async =>
      _solicitar('PUT', '${ruta}agente/', {'habilitado': habilitado});

  Future<List<PedidoResumen>> listar() async {
    final data = await _solicitar('GET', ruta);
    return (data['pedidos'] as List)
        .map((e) => PedidoResumen.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  Future<Pedido> obtener(String id) async =>
      Pedido.fromJson(await _solicitar('GET', '$ruta$id/'));
  Future<Pedido> revisar(String id, Map<String, dynamic> cuerpo) async =>
      Pedido.fromJson(await _solicitar('PUT', '$ruta$id/renglones/', cuerpo));
  Future<Pedido> publicar(String id, Map<String, dynamic> cuerpo) async =>
      Pedido.fromJson(
        await _solicitar('POST', '$ruta$id/cotizaciones/', cuerpo),
      );

  Future<Pedido> cobro(String id, Map<String, dynamic> cuerpo) async =>
      Pedido.fromJson(await _solicitar('POST', '$ruta$id/cobro/', cuerpo));
  Future<Pedido> listo(String id, Map<String, dynamic> cuerpo) async =>
      Pedido.fromJson(await _solicitar('POST', '$ruta$id/listo/', cuerpo));
  Future<Pedido> entregado(String id, Map<String, dynamic> cuerpo) async =>
      Pedido.fromJson(await _solicitar('POST', '$ruta$id/entregado/', cuerpo));

  Future<Map<String, dynamic>> _solicitar(
    String metodo,
    String path, [
    Map<String, dynamic>? cuerpo,
  ]) async {
    try {
      final respuesta = await _dio.request<dynamic>(
        path,
        data: cuerpo,
        options: Options(method: metodo),
      );
      return _leer(respuesta.statusCode, respuesta.data);
    } on DioException catch (error) {
      if (error.response != null) {
        return _leer(error.response!.statusCode, error.response!.data);
      }
      throw PedidoException(
        'RED',
        null,
        'No pudimos conectar. Revisa tu conexión e intenta de nuevo.',
      );
    }
  }

  Map<String, dynamic> _leer(int? status, dynamic cuerpo) {
    final mapa = cuerpo is Map
        ? Map<String, dynamic>.from(cuerpo)
        : <String, dynamic>{};
    if (status != null &&
        status >= 200 &&
        status < 300 &&
        mapa['data'] is Map) {
      return Map<String, dynamic>.from(mapa['data'] as Map);
    }
    final codigo =
        mapa['codigo'] as String? ??
        (status == 401
            ? 'SESION_TERMINADA'
            : status != null && status >= 500
            ? 'SERVICIO_NO_DISPONIBLE'
            : 'ERROR');
    final mensaje = switch (codigo) {
      'SESION_TERMINADA' => 'Tu sesión terminó. Vuelve a entrar.',
      'PERMISO_DENEGADO' => 'No tienes permiso para este comercio.',
      'PEDIDO_NO_ACCESIBLE' => 'Este pedido ya no está disponible.',
      'VERSION_OBSOLETA' => 'El pedido cambió. Cargamos la versión más reciente; revisa y guarda de nuevo.',
      'RENGLON_PENDIENTE' => 'Faltan renglones por resolver.',
      'PEDIDO_CONGELADO' => 'Este pedido ya no se puede editar.',
      'CLAVE_REUTILIZADA' => 'No pudimos guardar. Intenta de nuevo.',
      'PAYLOAD_INVALIDO' => 'Revisa los datos de los renglones.',
      'PROVEEDOR_NO_DISPONIBLE' => 'El cobro no está habilitado todavía.',
      'CUENTA_NO_ACTIVE' => 'La cuenta no está activa para cobrar.',
      'DEMO_DESTINO_NO_PERMITIDO' => 'El destino no está permitido en demo.',
      'MODO_CAMBIO' => 'Cambió el modo de cobro. Revisa el pedido.',
      'ACEPTACION_REQUERIDA' => 'Se requiere una aceptación vigente.',
      'INTENCION_DISTINTA' => 'Ya existe un cobro con otra intención.',
      'PAGO_NO_CONFIRMADO' => 'El pago aún no está confirmado.',
      'PREPARACION_INVALIDA' => 'Primero márcalo listo.',
      'SERVICIO_NO_DISPONIBLE' =>
        'El servidor no está disponible. Intenta de nuevo.',
      _ => 'No pudimos completar la solicitud. Intenta de nuevo.',
    };
    throw PedidoException(
      codigo,
      status,
      mensaje,
      pedidoVersion: mapa['pedido_version'] as int?,
      errores: mapa['errores'] is Map
          ? Map<String, dynamic>.from(mapa['errores'] as Map)
          : {},
    );
  }
}
