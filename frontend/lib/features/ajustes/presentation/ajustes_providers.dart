import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../data/comercio_repository.dart';

final comercioRepositoryProvider = Provider<ComercioRepository>((ref) {
  final dio = ref.watch(dioProvider);
  return ComercioRepository(dio);
});
