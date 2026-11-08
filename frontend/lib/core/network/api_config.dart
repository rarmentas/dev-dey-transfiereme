import 'package:flutter/foundation.dart';

/// Resuelve la URL base del API (mismo origen en web o `API_BASE_URL`).
String resolveApiBaseUrl() {
  const desdeDefine = String.fromEnvironment('API_BASE_URL');
  if (desdeDefine.isNotEmpty) {
    return desdeDefine.endsWith('/')
        ? desdeDefine.substring(0, desdeDefine.length - 1)
        : desdeDefine;
  }
  if (kIsWeb) {
    return Uri.base.origin;
  }
  // En Android/iOS use `--dart-define=API_BASE_URL=...` (p. ej. emulador → host).
  return 'http://127.0.0.1:8000';
}
