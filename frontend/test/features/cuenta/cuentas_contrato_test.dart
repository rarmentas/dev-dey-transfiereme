import 'package:cody/features/cuenta/data/cuentas_repository.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const base = '/api/cuenta/cuentas/';
  Map<String, dynamic> cuenta() => {
    'cuenta': {'id': 'a', 'clabe_enmascarada': '****1234', 'version': 4},
  };
  for (final operacion in ['crear', 'registro', 'sync', 'default']) {
    test('$operacion usa ruta y payload del contrato', () async {
      RequestOptions? recibida;
      final dio = Dio();
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (o, h) {
            recibida = o;
            h.resolve(
              Response(
                requestOptions: o,
                statusCode: operacion == 'crear' ? 201 : 200,
                data: cuenta(),
              ),
            );
          },
        ),
      );
      final repo = CuentasRepository(dio);
      final resultado = switch (operacion) {
        'crear' => await repo.crear('000000000000000000'),
        'registro' => await repo.registrar('a', 'Ana', 'PERSON', 'tienda', 4),
        'sync' => await repo.sincronizar('a'),
        _ => await repo.elegirPredeterminada('a', 4),
      };
      expect(resultado.id, 'a');
      expect(recibida!.path, switch (operacion) {
        'crear' => base,
        'registro' => '${base}a/registro/',
        'sync' => '${base}a/sincronizar/',
        _ => '${base}a/predeterminada/',
      });
      expect(recibida!.method, 'POST');
      final cuerpo = Map<String, dynamic>.from(recibida!.data as Map);
      if (operacion == 'registro') {
        expect(cuerpo.remove('command_key'), isNotEmpty);
        expect(cuerpo, {
          'nombre': 'Ana',
          'entidad': 'PERSON',
          'alias': 'tienda',
          'expected_version': 4,
        });
      } else {
        expect(cuerpo, switch (operacion) {
          'crear' => {'clabe': '000000000000000000'},
          'sync' => <String, dynamic>{},
          _ => {'expected_version': 4},
        });
      }
    });
    for (final caso in [
      (400, 'PAYLOAD_INVALIDO'),
      (403, 'NO_ES_DUENO'),
      (404, 'CUENTA_NO_ENCONTRADA'),
      (409, 'VERSION_OBSOLETA'),
      (503, 'ERROR'),
    ]) {
      test('$operacion propaga ${caso.$1} por codigo', () async {
        final dio = Dio();
        dio.interceptors.add(
          InterceptorsWrapper(
            onRequest: (o, h) => h.resolve(
              Response(
                requestOptions: o,
                statusCode: caso.$1,
                data: {'codigo': caso.$2, 'detail': 'texto ajeno'},
              ),
            ),
          ),
        );
        final repo = CuentasRepository(dio);
        Future<dynamic> solicitar() => switch (operacion) {
          'crear' => repo.crear('0'),
          'registro' => repo.registrar('a', 'Ana', 'PERSON', '', 4),
          'sync' => repo.sincronizar('a'),
          _ => repo.elegirPredeterminada('a', 4),
        };
        await expectLater(
          solicitar(),
          throwsA(
            isA<CuentasException>()
                .having((e) => e.codigo, 'codigo', caso.$2)
                .having((e) => e.status, 'status', caso.$1),
          ),
        );
      });
    }
    test('$operacion reporta falla de red', () async {
      final dio = Dio();
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (o, h) => h.reject(
            DioException(
              requestOptions: o,
              type: DioExceptionType.connectionError,
            ),
          ),
        ),
      );
      final repo = CuentasRepository(dio);
      Future<dynamic> solicitar() => switch (operacion) {
        'crear' => repo.crear('0'),
        'registro' => repo.registrar('a', 'Ana', 'PERSON', '', 4),
        'sync' => repo.sincronizar('a'),
        _ => repo.elegirPredeterminada('a', 4),
      };
      await expectLater(
        solicitar(),
        throwsA(
          isA<CuentasException>().having((e) => e.codigo, 'codigo', 'RED'),
        ),
      );
    });
  }
  test(
    'registro conserva clave en red, cambia con payload y limpia en exito',
    () async {
      final claves = <String>[];
      var respuesta = 0;
      final dio = Dio();
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (o, h) {
            claves.add((o.data as Map)['command_key'] as String);
            if (respuesta++ < 3) {
              h.reject(
                DioException(
                  requestOptions: o,
                  type: DioExceptionType.connectionError,
                ),
              );
            } else {
              h.resolve(
                Response(requestOptions: o, statusCode: 200, data: cuenta()),
              );
            }
          },
        ),
      );
      final repo = CuentasRepository(dio);
      for (final nombre in ['Ana', 'Ana', 'Eva']) {
        await expectLater(
          repo.registrar('a', nombre, 'PERSON', '', 4),
          throwsA(isA<CuentasException>()),
        );
      }
      await repo.registrar('a', 'Eva', 'PERSON', '', 4);
      await repo.registrar('a', 'Eva', 'PERSON', '', 4);
      expect(claves[0], claves[1]);
      expect(claves[2], isNot(claves[1]));
      expect(claves[3], claves[2]);
      expect(claves[4], isNot(claves[3]));
    },
  );
  for (final codigo in ['VERSION_OBSOLETA', 'CLAVE_REUTILIZADA']) {
    test('registro $codigo limpia clave', () async {
      final claves = <String>[];
      final dio = Dio();
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (o, h) {
            claves.add((o.data as Map)['command_key'] as String);
            h.resolve(
              Response(
                requestOptions: o,
                statusCode: 409,
                data: {'codigo': codigo},
              ),
            );
          },
        ),
      );
      final repo = CuentasRepository(dio);
      for (var i = 0; i < 2; i++) {
        await expectLater(
          repo.registrar('a', 'Ana', 'PERSON', '', 4),
          throwsA(isA<CuentasException>()),
        );
      }
      expect(claves.first, isNot(claves.last));
    });
  }
  test('403 sin codigo es generico', () async {
    final dio = Dio();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (o, h) => h.resolve(
          Response(
            requestOptions: o,
            statusCode: 403,
            data: {'detail': 'texto variable'},
          ),
        ),
      ),
    );
    await expectLater(
      CuentasRepository(dio).listar(),
      throwsA(
        isA<CuentasException>()
            .having((e) => e.codigo, 'codigo', 'ERROR')
            .having(
              (e) => e.mensaje,
              'mensaje',
              'No pudimos completar la solicitud. Intenta de nuevo.',
            ),
      ),
    );
  });
}
