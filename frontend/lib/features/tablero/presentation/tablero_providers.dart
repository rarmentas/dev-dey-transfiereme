import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../data/tablero.dart';
import '../data/tablero_repository.dart';

final tableroRepositoryProvider = Provider<TableroRepository>((ref) {
  return TableroRepository(ref.watch(dioProvider));
});

/// Sin reintentos automáticos: la pantalla ofrece «Reintentar».
final tableroProvider = FutureProvider.autoDispose<Tablero>(
  (ref) => ref.watch(tableroRepositoryProvider).obtener(),
  retry: (_, _) => null,
);
