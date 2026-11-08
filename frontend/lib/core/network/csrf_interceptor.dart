import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import 'document_cookie.dart';

const _metodosConCsrf = {'POST', 'PUT', 'PATCH', 'DELETE'};

/// Añade `X-CSRFToken` cuando hay cookie `csrftoken` (web o jar en móvil).
class CsrfInterceptor extends Interceptor {
  CsrfInterceptor({this.cookieJar});

  final CookieJar? cookieJar;

  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    if (!_metodosConCsrf.contains(options.method.toUpperCase())) {
      handler.next(options);
      return;
    }
    final token = await _leerCsrfToken(options.uri);
    if (token != null && token.isNotEmpty) {
      options.headers['X-CSRFToken'] = token;
    }
    handler.next(options);
  }

  Future<String?> _leerCsrfToken(Uri uri) async {
    if (kIsWeb) {
      return _csrfDesdeDocumento();
    }
    final jar = cookieJar;
    if (jar == null) {
      return null;
    }
    final cookies = await jar.loadForRequest(uri);
    for (final c in cookies) {
      if (c.name == 'csrftoken') {
        return c.value;
      }
    }
    return null;
  }

  String? _csrfDesdeDocumento() => leerCsrfDesdeDocumento();
}
