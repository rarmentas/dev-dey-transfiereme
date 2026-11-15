import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../data/cuentas_repository.dart';

final cuentasRepositoryProvider = Provider<CuentasRepository>(
  (ref) => CuentasRepository(ref.watch(dioProvider)),
);
