const _diasCortos = ['LUN', 'MAR', 'MIÉ', 'JUE', 'VIE', 'SÁB', 'DOM'];
const _diasLargos = [
  'Lunes',
  'Martes',
  'Miércoles',
  'Jueves',
  'Viernes',
  'Sábado',
  'Domingo',
];
const _mesesCortos = [
  'ENE',
  'FEB',
  'MAR',
  'ABR',
  'MAY',
  'JUN',
  'JUL',
  'AGO',
  'SEP',
  'OCT',
  'NOV',
  'DIC',
];

/// `LUN 03 NOV`.
String fechaSobretitulo(DateTime dia) {
  final d = dia.day.toString().padLeft(2, '0');
  return '${_diasCortos[dia.weekday - 1]} $d ${_mesesCortos[dia.month - 1]}';
}

/// `Viernes`.
String nombreDia(DateTime dia) => _diasLargos[dia.weekday - 1];

/// Letra del día para el eje de la gráfica (L M M J V S D).
String inicialDia(DateTime dia) => 'LMMJVSD'[dia.weekday - 1];

/// Día civil de una fecha «naive» (quita la hora).
DateTime soloDia(DateTime fecha) => DateTime(fecha.year, fecha.month, fecha.day);

/// Monto con `$` y miles y siempre dos decimales (para sumas).
String montoDeCentavos(int centavos) {
  final negativo = centavos < 0;
  final abs = centavos.abs();
  final entero = (abs ~/ 100).toString();
  final dec = (abs % 100).toString().padLeft(2, '0');
  final buffer = StringBuffer();
  for (var i = 0; i < entero.length; i++) {
    if (i > 0 && (entero.length - i) % 3 == 0) buffer.write(',');
    buffer.write(entero[i]);
  }
  return '${negativo ? '-' : ''}\$$buffer.$dec';
}

/// Convierte `"12.50"` a centavos sin pasar por `double`.
int centavosDe(String monto) {
  final texto = monto.trim();
  final negativo = texto.startsWith('-');
  final cuerpo = negativo ? texto.substring(1) : texto;
  final partes = cuerpo.split('.');
  final entero = int.tryParse(partes[0]) ?? 0;
  var dec = partes.length > 1 ? partes[1] : '';
  dec = '${dec}00'.substring(0, 2);
  final c = entero * 100 + (int.tryParse(dec) ?? 0);
  return negativo ? -c : c;
}
