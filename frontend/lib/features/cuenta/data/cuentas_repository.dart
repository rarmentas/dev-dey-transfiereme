import 'package:dio/dio.dart';

import '../../pedidos/data/clave_comando.dart';
import 'cuenta_cobro.dart';

class CuentasException implements Exception {
  CuentasException(
    this.codigo,
    this.status,
    this.mensaje, {
    this.reintento = 0,
  });
  final String codigo, mensaje;
  final int? status;
  final int reintento;
}

class CuentasRepository {
  CuentasRepository(this._dio);
  final Dio _dio;
  final Map<String, ClaveComando> _claves = {};
  static const ruta = '/api/cuenta/cuentas/';

  Future<List<CuentaCobro>> listar() async {
    final data = await _pedir('GET', ruta);
    return (data['cuentas'] as List)
        .map((e) => CuentaCobro.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  Future<CuentaCobro> crear(String clabe) async =>
      _cuenta(await _pedir('POST', ruta, {'clabe': clabe}));
  Future<CuentaCobro> registrar(
    String id,
    String nombre,
    String entidad,
    String alias,
    int versionEsperada,
  ) async {
    final contenido = {
      'nombre': nombre,
      'entidad': entidad,
      if (alias.isNotEmpty) 'alias': alias,
      'expected_version': versionEsperada,
    };
    final clave = _claves.putIfAbsent(id, ClaveComando.new);
    try {
      final cuenta = _cuenta(
        await _pedir('POST', '$ruta$id/registro/', {
          ...contenido,
          'command_key': clave.para(contenido),
        }),
      );
      clave.limpiar();
      return cuenta;
    } on CuentasException catch (e) {
      if ((e.status != null && e.status! < 500) ||
          e.codigo == 'PEY_RECHAZO' ||
          e.codigo == 'ADAPTADOR_NO_PRODUCCION') {
        clave.limpiar();
      }
      rethrow;
    }
  }

  Future<CuentaCobro> sincronizar(String id) async =>
      _cuenta(await _pedir('POST', '$ruta$id/sincronizar/', {}));
  Future<CuentaCobro> elegirPredeterminada(
    String id,
    int versionEsperada,
  ) async => _cuenta(
    await _pedir('POST', '$ruta$id/predeterminada/', {
      'expected_version': versionEsperada,
    }),
  );
  CuentaCobro _cuenta(Map<String, dynamic> data) =>
      CuentaCobro.fromJson(Map<String, dynamic>.from(data['cuenta'] as Map));
  Future<Map<String, dynamic>> _pedir(
    String metodo,
    String path, [
    Map<String, dynamic>? cuerpo,
  ]) async {
    try {
      final r = await _dio.request<dynamic>(
        path,
        data: cuerpo,
        options: Options(method: metodo),
      );
      return _leer(r.statusCode, r.data);
    } on DioException catch (e) {
      if (e.response != null) {
        return _leer(e.response!.statusCode, e.response!.data);
      }
      throw CuentasException('RED', null, 'No pudimos conectar.');
    }
  }

  Map<String, dynamic> _leer(int? status, dynamic data) {
    final mapa = data is Map
        ? Map<String, dynamic>.from(data)
        : <String, dynamic>{};
    if (status != null && status >= 200 && status < 300) return mapa;
    final codigo =
        mapa['codigo'] as String? ??
        (status == 401 ? 'SESION_TERMINADA' : 'ERROR');
    final mensaje = switch (codigo) {
      'NO_ES_DUENO' => 'Solo el dueño administra cuentas.',
      'SESION_TERMINADA' => 'Tu sesión terminó. Vuelve a entrar.',
      'CLABE_INVALIDA' => 'La CLABE no es válida.',
      'CLABE_DUPLICADA' => 'Ya está guardada.',
      'REGISTRO_INCIERTO' ||
      'PEY_INCIERTO' => 'El registro no está confirmado. No lo repitas.',
      'CUENTA_NO_ELEGIBLE' => 'La cuenta no está lista para cobrar.',
      'VERSION_OBSOLETA' => 'La cuenta cambió. Actualizamos la lista.',
      'SYNC_PRONTO' => 'Espera antes de sincronizar de nuevo.',
      _ => 'No pudimos completar la solicitud. Intenta de nuevo.',
    };
    throw CuentasException(
      codigo,
      status,
      mensaje,
      reintento: mapa['reintento_en_segundos'] as int? ?? 0,
    );
  }
}
