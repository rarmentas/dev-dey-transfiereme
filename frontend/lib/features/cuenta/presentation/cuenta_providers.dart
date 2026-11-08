import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../data/clabe_repository.dart';

final clabeRepositoryProvider = Provider<ClabeRepository>((ref) {
  return ClabeRepository(ref.watch(dioProvider));
});
