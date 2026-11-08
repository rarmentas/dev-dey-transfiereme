/// Movimiento de lectura. `monto` se conserva como cadena del servidor.
class Movimiento {
  const Movimiento({
    required this.id,
    required this.monto,
    required this.concepto,
    required this.conceptoVisible,
    required this.canal,
    required this.estado,
    required this.origen,
    required this.creadoEn,
    this.pagadoEn,
  });

  final int id;
  final String monto;

  /// Concepto enviado al pagador. No cambia al renombrar.
  final String concepto;
  final String conceptoVisible;
  final String canal;
  final String estado;
  final String origen;
  final DateTime creadoEn;
  final DateTime? pagadoEn;

  static const origenDesarrollo = 'origen_desarrollo';

  factory Movimiento.fromJson(Map<String, dynamic> json) {
    return Movimiento(
      id: json['id'] as int,
      monto: json['monto'] as String,
      concepto:
          json['concepto'] as String? ??
          json['concepto_visible'] as String? ??
          '',
      conceptoVisible: json['concepto_visible'] as String? ?? '',
      canal: json['canal'] as String? ?? '',
      estado: json['estado'] as String? ?? '',
      origen: json['origen'] as String? ?? '',
      creadoEn: DateTime.parse(json['creado_en'] as String),
      pagadoEn: _leerFecha(json['pagado_en']),
    );
  }

  bool get esPrueba => origen == origenDesarrollo;

  /// El vendedor ya le puso un nombre distinto al que vio el pagador.
  bool get muestraEnviado => conceptoVisible != concepto;

  /// Fecha que ve el vendedor: el pago si ya existe, si no la de alta.
  DateTime get fechaMostrada => pagadoEn ?? creadoEn;

  String get etiquetaCanal => switch (canal) {
    'qr_general' => 'QR general',
    'qr_venta' => 'QR de venta',
    'notificacion' => 'Notificación',
    _ => canal,
  };

  String get etiquetaEstado => switch (estado) {
    'pendiente' => 'Pendiente',
    'pagado' => 'Pagado',
    'vencido' => 'Vencido',
    _ => estado,
  };

  /// Antepone `$` y separa miles. No pasa el monto por `double`.
  String get montoFormateado => formatearMonto(monto);

  String get fechaCorta => fechaCortaLocal(fechaMostrada);
}

DateTime? _leerFecha(Object? valor) {
  if (valor is! String || valor.isEmpty) {
    return null;
  }
  return DateTime.parse(valor);
}

String formatearMonto(String monto) {
  final texto = monto.trim();
  final negativo = texto.startsWith('-');
  final cuerpo = negativo ? texto.substring(1) : texto;
  final punto = cuerpo.indexOf('.');
  final entero = punto < 0 ? cuerpo : cuerpo.substring(0, punto);
  final resto = punto < 0 ? '' : cuerpo.substring(punto);
  final signo = negativo ? '-' : '';
  return '$signo\$${_conSeparadorDeMiles(entero)}$resto';
}

String _conSeparadorDeMiles(String entero) {
  if (!RegExp(r'^\d+$').hasMatch(entero)) {
    return entero;
  }
  final buffer = StringBuffer();
  for (var i = 0; i < entero.length; i++) {
    if (i > 0 && (entero.length - i) % 3 == 0) {
      buffer.write(',');
    }
    buffer.write(entero[i]);
  }
  return buffer.toString();
}

String fechaCortaLocal(DateTime fecha) {
  final local = fecha.toLocal();
  final dia = local.day.toString().padLeft(2, '0');
  final mes = local.month.toString().padLeft(2, '0');
  return '$dia/$mes/${local.year}';
}
