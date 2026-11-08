/// Días civiles de Ciudad de México.
///
/// El backend corta los días en `America/Mexico_City` (ver `zona` del
/// tablero). México no usa horario de verano desde 2022, así que la zona es
/// UTC−6 todo el año y basta un desfase fijo: no hace falta una base de zonas
/// horarias. Todo «hoy», semana, mes, agrupación por día y hora mostrada debe
/// salir de aquí, no de la zona del teléfono.
const Duration kDesfaseCdmx = Duration(hours: 6);

/// Ahora en CDMX, como `DateTime` «naive» (campos de reloj de CDMX, sin zona).
DateTime ahoraCdmx([DateTime? ahora]) {
  final u = (ahora ?? DateTime.now()).toUtc().subtract(kDesfaseCdmx);
  return DateTime(
    u.year,
    u.month,
    u.day,
    u.hour,
    u.minute,
    u.second,
    u.millisecond,
  );
}

/// Fecha civil (sin hora) que [instante] tiene en CDMX.
DateTime diaCdmx(DateTime instante) {
  final c = ahoraCdmx(instante);
  return DateTime(c.year, c.month, c.day);
}

/// `HH:MM` de [instante] en hora de CDMX.
String horaCdmx(DateTime instante) {
  final c = ahoraCdmx(instante);
  return '${c.hour.toString().padLeft(2, '0')}:'
      '${c.minute.toString().padLeft(2, '0')}';
}

/// Lunes de la semana de [dia] (día civil).
DateTime lunesDe(DateTime dia) =>
    DateTime(dia.year, dia.month, dia.day - (dia.weekday - 1));
