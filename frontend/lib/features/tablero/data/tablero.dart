import '../../movimientos/data/movimiento.dart';

/// Tablero de lectura. Los montos se quedan como cadena del servidor.
class Tablero {
  const Tablero({
    required this.zona,
    required this.confirmado,
    required this.desarrollo,
  });

  final String zona;
  final SeccionTablero confirmado;
  final SeccionTablero desarrollo;

  factory Tablero.fromJson(Map<String, dynamic> json) {
    return Tablero(
      zona: json['zona'] as String? ?? '',
      confirmado: SeccionTablero.fromJson(_mapa(json['confirmado'])),
      desarrollo: SeccionTablero.fromJson(_mapa(json['desarrollo'])),
    );
  }

  bool get estaVacio => confirmado.filas.isEmpty && desarrollo.filas.isEmpty;
}

class SeccionTablero {
  const SeccionTablero({required this.total, required this.filas});

  final String total;
  final List<FilaTablero> filas;

  factory SeccionTablero.fromJson(Map<String, dynamic> json) {
    final crudas = json['filas'];
    final filas = <FilaTablero>[];
    if (crudas is List) {
      for (final item in crudas) {
        filas.add(FilaTablero.fromJson(_mapa(item)));
      }
    }
    return SeccionTablero(total: json['total'] as String? ?? '', filas: filas);
  }

  String get totalFormateado => formatearMonto(total);
}

class FilaTablero {
  const FilaTablero({
    required this.dia,
    required this.canal,
    required this.concepto,
    required this.etiqueta,
    required this.total,
    required this.cantidad,
  });

  /// Fecha civil del día, sin hora ni zona.
  final DateTime dia;
  final String canal;
  final String concepto;
  final String etiqueta;
  final String total;
  final int cantidad;

  factory FilaTablero.fromJson(Map<String, dynamic> json) {
    return FilaTablero(
      dia: leerDiaTablero(json['dia'] as String),
      canal: json['canal'] as String? ?? '',
      concepto: json['concepto'] as String? ?? '',
      etiqueta: json['etiqueta'] as String? ?? '',
      total: json['total'] as String,
      cantidad: json['cantidad'] as int,
    );
  }

  String get totalFormateado => formatearMonto(total);

  String get diaCorto {
    final d = dia.day.toString().padLeft(2, '0');
    final m = dia.month.toString().padLeft(2, '0');
    return '$d/$m/${dia.year}';
  }
}

/// `YYYY-MM-DD` como fecha local de calendario, sin convertir de UTC.
DateTime leerDiaTablero(String texto) {
  final partes = texto.split('-');
  if (partes.length != 3) {
    throw FormatException('Día de tablero inválido: $texto');
  }
  return DateTime(
    int.parse(partes[0]),
    int.parse(partes[1]),
    int.parse(partes[2]),
  );
}

String isoDiaTablero(DateTime fecha) {
  final mes = fecha.month.toString().padLeft(2, '0');
  final dia = fecha.day.toString().padLeft(2, '0');
  return '${fecha.year}-$mes-$dia';
}

Map<String, dynamic> _mapa(Object? valor) {
  if (valor is Map<String, dynamic>) {
    return valor;
  }
  if (valor is Map) {
    return Map<String, dynamic>.from(valor);
  }
  throw FormatException('El tablero no trae un objeto JSON.');
}
