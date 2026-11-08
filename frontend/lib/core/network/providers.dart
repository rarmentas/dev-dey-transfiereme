import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'dio_factory.dart';

final dioFactoryProvider = Provider<DioFactory>((ref) {
  return DioFactory();
});

final dioProvider = Provider<Dio>((ref) {
  final factory = ref.watch(dioFactoryProvider);
  final dio = factory.create();
  ref.onDispose(dio.close);
  return dio;
});
