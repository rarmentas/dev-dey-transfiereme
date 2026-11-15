import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../data/pedido_repository.dart';

final pedidoRepositoryProvider = Provider<PedidoRepository>((ref) {
  return PedidoRepository(ref.watch(dioProvider));
});
