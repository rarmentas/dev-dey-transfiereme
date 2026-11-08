import 'package:dio/browser.dart';
import 'package:dio/dio.dart';

void aplicarCredencialesWeb(Dio dio) {
  dio.httpClientAdapter = BrowserHttpClientAdapter(withCredentials: true);
}
