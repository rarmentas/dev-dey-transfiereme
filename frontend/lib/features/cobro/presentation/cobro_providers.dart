import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../data/qr_general_repository.dart';

final qrGeneralRepositoryProvider = Provider<QrGeneralRepository>((ref) {
  return QrGeneralRepository(ref.watch(dioProvider));
});

/// Sin reintentos automáticos: la pantalla ofrece «Reintentar».
final qrGeneralProvider = FutureProvider.autoDispose<QrGeneralResultado>(
  (ref) => ref.watch(qrGeneralRepositoryProvider).obtener(),
  retry: (_, _) => null,
);
