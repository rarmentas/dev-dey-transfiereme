import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../network/providers.dart';
import 'sesion_repository.dart';

final sesionRepositoryProvider = Provider<SesionRepository>((ref) {
  return SesionRepository(ref.watch(dioProvider));
});
