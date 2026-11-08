import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../network/providers.dart';
import 'registro_olvido_repository.dart';
import 'sesion_repository.dart';

final sesionRepositoryProvider = Provider<SesionRepository>((ref) {
  return SesionRepository(ref.watch(dioProvider));
});

final registroOlvidoRepositoryProvider = Provider<RegistroOlvidoRepository>((
  ref,
) {
  return RegistroOlvidoRepository(ref.watch(dioProvider));
});
