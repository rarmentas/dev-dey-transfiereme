import 'package:cody/features/venta/data/venta_repository.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/mock_venta_api.dart';

void main() {
  for (final tipo in ['red', 'timeout', '503', '502']) {
    test(
      '$tipo conserva clave para el mismo payload y la cambia para otro',
      () async {
        final claves = <String>[];
        final dio = Dio();
        dio.interceptors.add(
          InterceptorsWrapper(
            onRequest: (o, h) {
              claves.add(o.headers['Idempotency-Key'] as String);
              if (tipo == 'red' || tipo == 'timeout') {
                h.reject(
                  DioException(
                    requestOptions: o,
                    type: tipo == 'red'
                        ? DioExceptionType.connectionError
                        : DioExceptionType.receiveTimeout,
                  ),
                );
              } else {
                h.resolve(
                  Response(
                    requestOptions: o,
                    statusCode: int.parse(tipo),
                    data: {'puede_haberse_creado': true},
                  ),
                );
              }
            },
          ),
        );
        final repo = VentaRepository(dio);
        for (final monto in ['1', '1', '2']) {
          await expectLater(
            repo.crear(monto: monto),
            throwsA(
              isA<PeyException>().having(
                (e) => e.puedeHaberseCreado,
                'incierto',
                true,
              ),
            ),
          );
        }
        expect(claves[0], isNotEmpty);
        expect(claves[1], claves[0]);
        expect(claves[2], isNot(claves[1]));
      },
    );
  }
  for (final respuesta in [201, 400, 409, 502]) {
    test('$respuesta limpia clave tras resultado definitivo', () async {
      final claves = <String>[];
      final dio = Dio();
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (o, h) {
            claves.add(o.headers['Idempotency-Key'] as String);
            h.resolve(
              Response(
                requestOptions: o,
                statusCode: respuesta,
                data: switch (respuesta) {
                  201 => cuerpoVenta(id: 7, estado: 'pendiente'),
                  409 => {'codigo': 'CLAVE_REUTILIZADA'},
                  502 => {'puede_haberse_creado': false},
                  _ => {'codigo': 'ValidacionVenta'},
                },
              ),
            );
          },
        ),
      );
      final repo = VentaRepository(dio);
      for (var i = 0; i < 2; i++) {
        if (respuesta == 201) {
          expect((await repo.crear(monto: '1')).movimientoId, 7);
        } else {
          await expectLater(repo.crear(monto: '1'), throwsA(isA<Exception>()));
        }
      }
      expect(claves.first, isNot(claves.last));
    });
  }
  test('502 sin indicador se considera incierto', () async {
    final dio = Dio();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (o, h) =>
            h.resolve(Response(requestOptions: o, statusCode: 502, data: {})),
      ),
    );
    await expectLater(
      VentaRepository(dio).crear(monto: '1'),
      throwsA(
        isA<PeyException>().having(
          (e) => e.puedeHaberseCreado,
          'incierto',
          true,
        ),
      ),
    );
  });
  for (final codigo in ['COBRO_EN_CURSO', 'COBRO_INCIERTO']) {
    test('$codigo no se interpreta como cuenta inactiva', () async {
      final dio = Dio();
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (o, h) => h.resolve(
            Response(
              requestOptions: o,
              statusCode: 409,
              data: {'codigo': codigo},
            ),
          ),
        ),
      );
      await expectLater(
        VentaRepository(dio).crear(monto: '1'),
        throwsA(
          isA<VentaApiException>().having(
            (e) => e.mensaje,
            'mensaje',
            contains('no lo repitas'),
          ),
        ),
      );
    });
  }
  test('403 demo usa codigo estable', () async {
    final dio = Dio();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (o, h) => h.resolve(
          Response(
            requestOptions: o,
            statusCode: 403,
            data: {'codigo': 'RUTA_BLOQUEADA_EN_DEMO', 'detail': 'otro'},
          ),
        ),
      ),
    );
    await expectLater(
      VentaRepository(dio).crear(monto: '1'),
      throwsA(
        isA<VentaApiException>().having(
          (e) => e.mensaje,
          'mensaje',
          contains('demo'),
        ),
      ),
    );
  });

  for (final status in [401, 403]) {
    test('$status sesion terminada tiene aviso estable', () async {
      final dio = Dio();
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (o, h) => h.resolve(
            Response(
              requestOptions: o,
              statusCode: status,
              data: {'codigo': 'SESION_TERMINADA', 'detail': 'otro'},
            ),
          ),
        ),
      );
      await expectLater(
        VentaRepository(dio).crear(monto: '1'),
        throwsA(
          isA<VentaApiException>().having(
            (e) => e.mensaje,
            'mensaje',
            'Tu sesión terminó. Vuelve a entrar.',
          ),
        ),
      );
    });
  }
  test('cambiar telefono y ruta genera claves distintas', () async {
    final claves = <String>[];
    final dio = Dio();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (o, h) {
          claves.add(o.headers['Idempotency-Key'] as String);
          h.reject(
            DioException(
              requestOptions: o,
              type: DioExceptionType.connectionError,
            ),
          );
        },
      ),
    );
    final repo = VentaRepository(dio);
    await expectLater(
      repo.crearNotificacion(monto: '1', telefono: '5512345678'),
      throwsA(isA<PeyException>()),
    );
    await expectLater(
      repo.crearNotificacion(monto: '1', telefono: '5512345679'),
      throwsA(isA<PeyException>()),
    );
    await expectLater(repo.crear(monto: '1'), throwsA(isA<PeyException>()));
    expect(claves.toSet().length, 3);
  });
}
