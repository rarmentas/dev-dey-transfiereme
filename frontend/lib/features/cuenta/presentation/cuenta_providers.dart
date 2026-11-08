import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../data/clabe_repository.dart';
import '../data/cuenta_estado.dart';
import '../data/cuenta_estado_repository.dart';

final clabeRepositoryProvider = Provider<ClabeRepository>((ref) {
  return ClabeRepository(ref.watch(dioProvider));
});

final cuentaEstadoRepositoryProvider = Provider<CuentaEstadoRepository>((ref) {
  return CuentaEstadoRepository(ref.watch(dioProvider));
});

final cuentaEstadoProvider = FutureProvider<EstadoCuentaPey>((ref) async {
  final repo = ref.watch(cuentaEstadoRepositoryProvider);
  return repo.obtenerEstado();
});
