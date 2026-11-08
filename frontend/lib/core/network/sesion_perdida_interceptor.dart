import 'package:dio/dio.dart';

const mensajeDebeIniciarSesion = 'Debe iniciar sesión.';

/// Notifica cuando el API responde 403 por sesión caducada.
class SesionPerdidaInterceptor extends Interceptor {
  SesionPerdidaInterceptor({this.onSesionPerdida});

  void Function()? onSesionPerdida;

  @override
  void onResponse(
    Response<dynamic> response,
    ResponseInterceptorHandler handler,
  ) {
    _revisarSesionPerdida(response.requestOptions.uri.path, response.statusCode,
        response.data);
    handler.next(response);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    _revisarSesionPerdida(
      err.requestOptions.uri.path,
      err.response?.statusCode,
      err.response?.data,
    );
    handler.next(err);
  }

  void _revisarSesionPerdida(String path, int? status, dynamic data) {
    if (status != 403 || data is! Map<String, dynamic>) {
      return;
    }
    if (data['detail'] != mensajeDebeIniciarSesion) {
      return;
    }
    if (path.contains('/api/sesion/estado/') ||
        path.contains('/api/sesion/entrar/')) {
      return;
    }
    onSesionPerdida?.call();
  }
}
