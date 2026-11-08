import '../../../core/fecha/dia_cdmx.dart';
import '../../movimientos/data/movimiento.dart';
import '../../tablero/data/tablero.dart';

/// Lo que muestra «Hoy llevas» y los últimos cobros en Inicio.
class InicioResumen {
  const InicioResumen({
    required this.totalHoy,
    required this.cobrosHoy,
    required this.pendientesHoy,
    required this.recientes,
  });

  /// Total confirmado de hoy, ya con `$` y miles.
  final String totalHoy;
  final int cobrosHoy;
  final int pendientesHoy;

  /// Hasta tres movimientos, del más reciente al más antiguo.
  final List<Movimiento> recientes;

  bool get sinCobros => recientes.isEmpty && cobrosHoy == 0;

  factory InicioResumen.desde({
    required Tablero tablero,
    required List<Movimiento> movimientos,
    required DateTime hoy,
  }) {
    final cobros = tablero.confirmado.filas.fold<int>(
      0,
      (suma, fila) => suma + fila.cantidad,
    );
    final pendientes = movimientos
        .where((m) => m.estado == 'pendiente' && _mismoDia(m.fechaMostrada, hoy))
        .length;
    final ordenados = [...movimientos]
      ..sort((a, b) => b.fechaMostrada.compareTo(a.fechaMostrada));
    final total = tablero.confirmado.total.trim();
    return InicioResumen(
      totalHoy: formatearMonto(total.isEmpty ? '0.00' : total),
      cobrosHoy: cobros,
      pendientesHoy: pendientes,
      recientes: ordenados.take(3).toList(),
    );
  }
}

bool _mismoDia(DateTime fecha, DateTime hoy) {
  final dia = diaCdmx(fecha);
  return dia.year == hoy.year && dia.month == hoy.month && dia.day == hoy.day;
}
