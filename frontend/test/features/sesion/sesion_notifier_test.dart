import 'package:cody/core/network/providers.dart';
import 'package:cody/core/sesion/sesion_notifier.dart';
import 'package:cody/core/sesion/sesion_providers.dart';
import 'package:cody/core/sesion/sesion_repository.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/mock_sesion_api.dart';

void _interceptorFallaRed(Dio dio, {bool Function(RequestOptions)? soloSi}) {
  dio.interceptors.insert(
    0,
    InterceptorsWrapper(
      onRequest: (options, handler) {
        if (soloSi != null && !soloSi(options)) {
          handler.next(options);
          return;
        }
        handler.reject(
          DioException(
            requestOptions: options,
            type: DioExceptionType.connectionError,
            message: 'sin red',
          ),
        );
      },
    ),
  );
}

void main() {
  test('entrar deja sesión autenticada', () async {
    final dio = crearDioPrueba();
    prepararDioConSesion(dio);

    final container = ProviderContainer(
      overrides: [
        dioProvider.overrideWithValue(dio),
        sesionRepositoryProvider.overrideWith(
          (ref) => SesionRepository(dio),
        ),
      ],
    );
    addTearDown(container.dispose);

    await container.read(sesionNotifierProvider.notifier).refrescarAlArranque();
    final ok = await container.read(sesionNotifierProvider.notifier).entrar(
          correo: 'lupe@tortilleria.mx',
          contrasena: 'clave',
        );
    expect(ok, isTrue);
    expect(container.read(sesionNotifierProvider).autenticado, isTrue);
  });

  test('entrar rechazado muestra detalle', () async {
    final dio = crearDioPrueba();
    final sim = prepararDioConSesion(dio);
    sim.rechazarEntrada = true;

    final container = ProviderContainer(
      overrides: [
        dioProvider.overrideWithValue(dio),
        sesionRepositoryProvider.overrideWith(
          (ref) => SesionRepository(dio),
        ),
      ],
    );
    addTearDown(container.dispose);

    final ok = await container.read(sesionNotifierProvider.notifier).entrar(
          correo: 'mal@ejemplo.mx',
          contrasena: 'incorrecta',
        );
    expect(ok, isFalse);
    expect(
      container.read(sesionNotifierProvider).errorMensaje,
      'Revise el correo y la contraseña.',
    );
  });

  test('cargarEstado con fallo de red no deja cargando', () async {
    final dio = crearDioPrueba();
    _interceptorFallaRed(dio);

    final container = ProviderContainer(
      overrides: [
        dioProvider.overrideWithValue(dio),
        sesionRepositoryProvider.overrideWith(
          (ref) => SesionRepository(dio),
        ),
      ],
    );
    addTearDown(container.dispose);

    final notifier = container.read(sesionNotifierProvider.notifier);
    await notifier.refrescarAlArranque();
    await Future<void>.delayed(Duration.zero);
    final s = container.read(sesionNotifierProvider);
    expect(s.cargando, isFalse);
    expect(s.resuelto, isTrue);
    expect(s.errorMensaje, contains('conectar'));
  });

  test('entrar con fallo de red permite reintentar', () async {
    final dio = crearDioPrueba();
    prepararDioConSesion(dio);
    var fallarEntrar = true;
    _interceptorFallaRed(
      dio,
      soloSi: (o) =>
          fallarEntrar &&
          o.method == 'POST' &&
          o.path.contains('/api/sesion/entrar'),
    );

    final container = ProviderContainer(
      overrides: [
        dioProvider.overrideWithValue(dio),
        sesionRepositoryProvider.overrideWith(
          (ref) => SesionRepository(dio),
        ),
      ],
    );
    addTearDown(container.dispose);

    await container.read(sesionNotifierProvider.notifier).refrescarAlArranque();

    var ok = await container.read(sesionNotifierProvider.notifier).entrar(
          correo: 'lupe@tortilleria.mx',
          contrasena: 'clave',
        );
    expect(ok, isFalse);
    var s = container.read(sesionNotifierProvider);
    expect(s.cargando, isFalse);
    expect(s.errorMensaje, isNotNull);

    fallarEntrar = false;
    ok = await container.read(sesionNotifierProvider.notifier).entrar(
          correo: 'lupe@tortilleria.mx',
          contrasena: 'clave',
        );
    expect(ok, isTrue);
    s = container.read(sesionNotifierProvider);
    expect(s.cargando, isFalse);
    expect(s.autenticado, isTrue);
  });

  test('salir con fallo de red cierra la sesión local', () async {
    final dio = crearDioPrueba();
    final sim = prepararDioConSesion(dio);
    sim.autenticado = true;
    _interceptorFallaRed(
      dio,
      soloSi: (o) => o.method == 'POST' && o.path.contains('/api/sesion/salir'),
    );

    final container = ProviderContainer(
      overrides: [
        dioProvider.overrideWithValue(dio),
        sesionRepositoryProvider.overrideWith(
          (ref) => SesionRepository(dio),
        ),
      ],
    );
    addTearDown(container.dispose);

    await container.read(sesionNotifierProvider.notifier).refrescarAlArranque();
    expect(container.read(sesionNotifierProvider).autenticado, isTrue);

    await container.read(sesionNotifierProvider.notifier).salir();
    final s = container.read(sesionNotifierProvider);
    expect(s.cargando, isFalse);
    expect(s.autenticado, isFalse);
  });
}
