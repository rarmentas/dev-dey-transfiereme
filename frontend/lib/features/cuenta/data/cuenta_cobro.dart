class CuentaCobro {
  CuentaCobro.fromJson(Map<String, dynamic> json)
    : id = json['id'] as String,
      clabe = enmascararClabe(json['clabe_enmascarada'] as String? ?? ''),
      registro = json['registro_estado'] as String? ?? 'sin_registro',
      status = json['codi_status'] as String? ?? 'pending',
      predeterminada = json['es_predeterminada'] == true,
      puedeCobrar = json['puede_cobrar'] == true,
      version = json['version'] as int? ?? 0;
  final String id, clabe, registro, status;
  final bool predeterminada, puedeCobrar;
  final int version;
}

String enmascararClabe(String valor) {
  final digitos = valor.replaceAll(RegExp(r'\D'), '');
  return digitos.length > 4
      ? '••••${digitos.substring(digitos.length - 4)}'
      : valor;
}
