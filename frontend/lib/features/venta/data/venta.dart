/// Venta de lectura. `monto` se conserva como cadena del servidor.
class Venta {
  const Venta({
    required this.movimientoId,
    required this.canal,
    required this.estado,
    required this.monto,
    required this.concepto,
    required this.qrString,
    this.venceEn,
    this.pagadoEn,
    this.cobroId,
    this.origen,
  });

  final int movimientoId;
  final String canal;
  final String estado;
  final String monto;
  final String concepto;
  final String qrString;
  final DateTime? venceEn;
  final DateTime? pagadoEn;
  final int? cobroId;
  final String? origen;

  factory Venta.fromJson(Map<String, dynamic> json) {
    return Venta(
      movimientoId: json['movimiento_id'] as int,
      canal: json['canal'] as String? ?? '',
      estado: json['estado'] as String? ?? '',
      monto: json['monto'] as String,
      concepto: json['concepto'] as String? ?? '',
      qrString: json['qr_string'] as String? ?? '',
      venceEn: _leerFecha(json['vence_en']),
      pagadoEn: _leerFecha(json['pagado_en']),
      cobroId: json['cobro_id'] as int?,
      origen: json['origen'] as String?,
    );
  }

  bool get esPendiente => estado == 'pendiente';
  bool get esPagado => estado == 'pagado';
  bool get esVencido => estado == 'vencido';
  bool get esTerminal => esPagado || esVencido;

  String get horaPagado {
    final momento = pagadoEn;
    if (momento == null) {
      return '';
    }
    return horaLocalCorta(momento);
  }
}

DateTime? _leerFecha(Object? valor) {
  if (valor is! String || valor.isEmpty) {
    return null;
  }
  return DateTime.parse(valor);
}

String horaLocalCorta(DateTime fecha) {
  final local = fecha.toLocal();
  final hora = local.hour.toString().padLeft(2, '0');
  final minuto = local.minute.toString().padLeft(2, '0');
  return '$hora:$minuto';
}

/// Cuenta regresiva `mm:ss` hasta [vence]. No usa `double`.
String cuentaRegresiva(DateTime vence, DateTime ahora) {
  final resta = vence.difference(ahora);
  final total = resta.isNegative ? 0 : resta.inSeconds;
  final minutos = (total ~/ 60).toString().padLeft(2, '0');
  final segundos = (total % 60).toString().padLeft(2, '0');
  return '$minutos:$segundos';
}

/// Monto escrito por el vendedor. Vacío si es válido; si no, el mensaje.
String? validarMontoVenta(String texto) {
  final limpio = texto.trim();
  if (limpio.isEmpty) {
    return 'Indique el monto.';
  }
  if (!RegExp(r'^\d+(\.\d+)?$').hasMatch(limpio)) {
    return 'El monto debe ser un número.';
  }
  final partes = limpio.split('.');
  if (partes.length == 2 && partes[1].length > 2) {
    return 'El monto no admite más de 2 decimales.';
  }
  final entero = partes[0].replaceFirst(RegExp(r'^0+'), '');
  final fraccion = partes.length == 2 ? partes[1].replaceAll('0', '') : '';
  if (entero.isEmpty && fraccion.isEmpty) {
    return 'El monto debe ser mayor que 0.';
  }
  return null;
}

/// Referencia vacía es válida. Si viene, 1 a 7 dígitos.
String? validarReferenciaVenta(String texto) {
  final limpio = texto.trim();
  if (limpio.isEmpty) {
    return null;
  }
  if (!RegExp(r'^\d{1,7}$').hasMatch(limpio)) {
    return 'La referencia debe ser numérica, de 1 a 7 dígitos.';
  }
  return null;
}
