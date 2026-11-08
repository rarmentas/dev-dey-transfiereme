import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio/dio.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';
import 'package:flutter/foundation.dart';

import 'api_config.dart';
import 'csrf_interceptor.dart';
import 'dio_web_credentials.dart';
import 'sesion_perdida_interceptor.dart';

class DioFactory {
  DioFactory({
    this.onSesionPerdida,
    CookieJar? cookieJar,
  }) : _cookieJar = cookieJar ?? CookieJar();

  final CookieJar _cookieJar;
  void Function()? onSesionPerdida;

  CookieJar get cookieJar => _cookieJar;

  Dio create() {
    final baseUrl = resolveApiBaseUrl();
    final dio = Dio(
      BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: const Duration(seconds: 10),
        sendTimeout: const Duration(seconds: 30),
        receiveTimeout: const Duration(seconds: 30),
        headers: const {'Accept': 'application/json'},
        validateStatus: (status) => status != null && status < 500,
      ),
    );

    final sesionPerdida = SesionPerdidaInterceptor(onSesionPerdida: () {
      onSesionPerdida?.call();
    });
    dio.interceptors.add(sesionPerdida);

    if (kIsWeb) {
      aplicarCredencialesWeb(dio);
    } else {
      dio.interceptors.add(CookieManager(_cookieJar));
    }
    dio.interceptors.add(CsrfInterceptor(cookieJar: kIsWeb ? null : _cookieJar));

    return dio;
  }
}
