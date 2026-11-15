class CuentaCobro {
  CuentaCobro.fromJson(Map<String, dynamic> json)
    : id = json['id'] as String,
      clabe = enmascararClabe(json['clabe_enmascarada'] as String? ?? ''),
      registro = json['registro_estado'] as String? ?? 'sin_registro',
      status = json['codi_status'] as String? ?? 'pending',
      predeterminada = json['es_predeterminada'] == true,
      puedeCobrar = json['puede_cobrar'] == true,
      sincronizadaEn = json['sincronizada_en'] as String?,
      ultimoError = _protegerClabe(json['ultimo_error'] as String? ?? ''),
      anomalia = _protegerClabe(json['anomalia'] as String? ?? ''),
      operacionTipo = json['operacion'] is Map
          ? (json['operacion'] as Map)['tipo'] as String?
          : null,
      operacionEstado = json['operacion'] is Map
          ? (json['operacion'] as Map)['estado'] as String?
          : null,
      version = json['version'] as int? ?? 0;
  final String id, clabe, registro, status;
  final bool predeterminada, puedeCobrar;
  final String? sincronizadaEn, operacionTipo, operacionEstado;
  final String ultimoError, anomalia;
  final int version;
}

String enmascararClabe(String valor) {
  final digitos = valor.replaceAll(RegExp(r'\D'), '');
  return digitos.length > 4
      ? '••••${digitos.substring(digitos.length - 4)}'
      : valor;
}

String _protegerClabe(String valor) => valor.replaceAllMapped(
  RegExp(r'(?<!\d)\d{18}(?!\d)'),
  (coincidencia) => enmascararClabe(coincidencia.group(0)!),
);
