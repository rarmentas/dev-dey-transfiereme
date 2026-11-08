import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/fecha/dia_cdmx.dart';
import '../../movimientos/data/movimiento.dart';
import '../../movimientos/presentation/movimientos_providers.dart';
import '../../tablero/data/tablero.dart';
import '../../tablero/presentation/tablero_providers.dart';
import '../data/inicio_resumen.dart';

/// Resumen de Inicio. Sin reintentos automáticos: la pantalla ofrece «Reintentar».
final inicioResumenProvider = FutureProvider.autoDispose<InicioResumen>(
  (ref) async {
    final dia = diaCdmx(DateTime.now());
    final resultados = await Future.wait<Object>([
      ref.watch(tableroRepositoryProvider).obtener(desde: dia, hasta: dia),
      ref.watch(movimientosRepositoryProvider).listar(),
    ]);
    return InicioResumen.desde(
      tablero: resultados[0] as Tablero,
      movimientos: resultados[1] as List<Movimiento>,
      hoy: dia,
    );
  },
  retry: (_, _) => null,
);
