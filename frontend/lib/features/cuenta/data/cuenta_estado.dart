class EstadoCuentaPey {
  const EstadoCuentaPey({
    required this.fase,
    required this.paso,
    required this.codiStatus,
    required this.puedeCobrar,
    required this.clabeEnmascarada,
    required this.tieneCuentaPey,
    required this.peyBankAccountIdSufijo,
    this.actualizadoEn,
  });

  final String fase;
  final int? paso;
  final String codiStatus;
  final bool puedeCobrar;
  final String clabeEnmascarada;
  final bool tieneCuentaPey;
  final String peyBankAccountIdSufijo;
  final String? actualizadoEn;

  factory EstadoCuentaPey.fromJson(Map<String, dynamic> json) {
    final pasoRaw = json['paso'];
    int? paso;
    if (pasoRaw is int) {
      paso = pasoRaw;
    }
    return EstadoCuentaPey(
      fase: json['fase'] as String? ?? 'sin_clabe',
      paso: paso,
      codiStatus: json['codi_status'] as String? ?? 'pending',
      puedeCobrar: json['puede_cobrar'] == true,
      clabeEnmascarada: json['clabe_enmascarada'] as String? ?? '',
      tieneCuentaPey: json['tiene_cuenta_pey'] == true,
      peyBankAccountIdSufijo:
          json['pey_bank_account_id_sufijo'] as String? ?? '',
      actualizadoEn: json['actualizado_en'] as String?,
    );
  }
}

class CuentaPeyApiException implements Exception {
  CuentaPeyApiException(this.mensaje, {this.codigo});

  final String mensaje;
  final String? codigo;

  @override
  String toString() => mensaje;
}
