import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/fecha/dia_cdmx.dart';
import '../../../core/network/providers.dart';
import '../data/movimiento.dart';
import '../data/movimientos_repository.dart';

final movimientosRepositoryProvider = Provider<MovimientosRepository>((ref) {
  return MovimientosRepository(ref.watch(dioProvider));
});

/// Sin reintentos automáticos: la pantalla ofrece «Reintentar».
final movimientosProvider = FutureProvider.autoDispose<List<Movimiento>>(
  (ref) => ref.watch(movimientosRepositoryProvider).listar(),
  retry: (_, _) => null,
);

/// Reloj de la pantalla de movimientos (hora de CDMX «naive»); las pruebas lo sustituyen.
final movimientosAhoraProvider = Provider<DateTime>((ref) => ahoraCdmx());
