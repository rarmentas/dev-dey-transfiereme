import 'package:dio/dio.dart';

Dio crearDioPrueba({String baseUrl = 'http://test'}) {
  final dio = Dio(
    BaseOptions(
      baseUrl: baseUrl,
      headers: const {'Accept': 'application/json'},
      validateStatus: (status) => status != null && status < 500,
    ),
  );
  return dio;
}

class SimuladorSesion {
  bool autenticado = false;
  bool rechazarEntrada = false;
  int llamadasEstado = 0;

  Map<String, dynamic> get cuerpoEstado => {
        'usuario': 'lupe@tortilleria.mx',
        'correo': 'lupe@tortilleria.mx',
        'nombre': 'Lupe',
        'apellidos': 'García',
        'comercio': {'id': 1, 'nombre': 'Tortillería La Esperanza'},
      };
}

void instalarSimuladorSesion(Dio dio, SimuladorSesion sim) {
  dio.interceptors.insert(
    0,
    InterceptorsWrapper(
      onRequest: (options, handler) {
        final path = options.path;
        if (path.contains('/api/sesion/estado')) {
          sim.llamadasEstado++;
          if (sim.autenticado) {
            handler.resolve(
              Response(
                requestOptions: options,
                statusCode: 200,
                data: sim.cuerpoEstado,
              ),
            );
          } else {
            handler.resolve(
              Response(
                requestOptions: options,
                statusCode: 403,
                data: {'detail': 'Debe iniciar sesión.'},
              ),
            );
          }
          return;
        }
        if (path.contains('/api/sesion/entrar') && options.method == 'POST') {
          if (sim.rechazarEntrada) {
            handler.resolve(
              Response(
                requestOptions: options,
                statusCode: 403,
                data: {'detail': 'Revise el correo y la contraseña.'},
              ),
            );
            return;
          }
          sim.autenticado = true;
          handler.resolve(
            Response(
              requestOptions: options,
              statusCode: 200,
              data: {'usuario': 'lupe@tortilleria.mx'},
            ),
          );
          return;
        }
        if (path.contains('/api/sesion/salir') && options.method == 'POST') {
          sim.autenticado = false;
          handler.resolve(
            Response(
              requestOptions: options,
              statusCode: 200,
              data: <String, dynamic>{},
            ),
          );
          return;
        }
        handler.next(options);
      },
    ),
  );
}

SimuladorSesion prepararDioConSesion(Dio dio) {
  final sim = SimuladorSesion();
  instalarSimuladorSesion(dio, sim);
  return sim;
}
