import 'package:cody/core/network/providers.dart';
import 'package:cody/core/sesion/sesion_notifier.dart';
import 'package:cody/core/sesion/sesion_providers.dart';
import 'package:cody/core/sesion/sesion_repository.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/mock_sesion_api.dart';

void main() {
  test('cargarEstado lee el nombre de comercio persistido en el servidor', () async {
    var nombreComercio = 'Comercio inicial';
    final dio = crearDioPrueba();
    dio.interceptors.insert(
      0,
      InterceptorsWrapper(
        onRequest: (options, handler) {
          if (options.path.contains('/api/sesion/estado')) {
            handler.resolve(
              Response(
                requestOptions: options,
                statusCode: 200,
                data: {
                  'usuario': 'vendedor@demo.mx',
                  'correo': 'vendedor@demo.mx',
                  'nombre': 'Ada',
                  'apellidos': '',
                  'comercio': {'id': 1, 'nombre': nombreComercio},
                },
              ),
            );
            return;
          }
          handler.next(options);
        },
      ),
    );

    final container = ProviderContainer(
      overrides: [
        dioProvider.overrideWithValue(dio),
        sesionRepositoryProvider.overrideWith((ref) => SesionRepository(dio)),
      ],
    );
    addTearDown(container.dispose);

    final notifier = container.read(sesionNotifierProvider.notifier);
    await notifier.cargarEstado();
    expect(
      container.read(sesionNotifierProvider).estado?.comercio?.nombre,
      'Comercio inicial',
    );

    nombreComercio = 'Nombre persistido tras PATCH';
    await notifier.cargarEstado();
    expect(
      container.read(sesionNotifierProvider).estado?.comercio?.nombre,
      'Nombre persistido tras PATCH',
    );
  });
}
