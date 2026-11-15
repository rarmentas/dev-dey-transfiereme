import 'package:cody/features/pedidos/data/pedido_repository.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/mock_pedido_api.dart';

void main() {
  for (final accion in ['cobro', 'listo', 'entregado']) {
    for (final caso in [
      (400, 'PAYLOAD_INVALIDO'),
      (401, 'SESION_TERMINADA'),
      (403, 'PERMISO_DENEGADO'),
      (404, 'PEDIDO_NO_ACCESIBLE'),
      (409, 'VERSION_OBSOLETA'),
      (409, 'CLAVE_REUTILIZADA'),
      (503, 'SERVICIO_NO_DISPONIBLE'),
    ]) {
      test('$accion ${caso.$1} ${caso.$2} usa codigo', () async {
        final dio = Dio();
        dio.interceptors.add(
          InterceptorsWrapper(
            onRequest: (o, h) {
              expect(o.path, '/api/pedidos/abc/$accion/');
              expect(o.data, {'expected_version': 1, 'command_key': 'clave'});
              h.resolve(
                Response(
                  requestOptions: o,
                  statusCode: caso.$1,
                  data: {'codigo': caso.$2, 'detail': 'texto ajeno'},
                ),
              );
            },
          ),
        );
        final repo = PedidoRepository(dio);
        final cuerpo = {'expected_version': 1, 'command_key': 'clave'};
        final futuro = switch (accion) {
          'cobro' => repo.cobro('abc', cuerpo),
          'listo' => repo.listo('abc', cuerpo),
          _ => repo.entregado('abc', cuerpo),
        };
        await expectLater(
          futuro,
          throwsA(
            isA<PedidoException>()
                .having((e) => e.codigo, 'codigo', caso.$2)
                .having((e) => e.status, 'status', caso.$1),
          ),
        );
      });
    }
    test('$accion red devuelve error de conexion', () async {
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
      final repo = PedidoRepository(dio);
      final futuro = switch (accion) {
        'cobro' => repo.cobro('abc', {}),
        'listo' => repo.listo('abc', {}),
        _ => repo.entregado('abc', {}),
      };
      await expectLater(
        futuro,
        throwsA(
          isA<PedidoException>().having((e) => e.codigo, 'codigo', 'RED'),
        ),
      );
    });
    test('$accion exito devuelve DTO', () async {
      final dio = Dio();
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (o, h) => h.resolve(
            Response(
              requestOptions: o,
              statusCode: 200,
              data: exito(pedidoJson(aceptado: true)),
            ),
          ),
        ),
      );
      final repo = PedidoRepository(dio);
      final resultado = switch (accion) {
        'cobro' => await repo.cobro('abc', {}),
        'listo' => await repo.listo('abc', {}),
        _ => await repo.entregado('abc', {}),
      };
      expect(resultado.id, 'abc');
      expect(resultado.aceptado, isTrue);
    });
  }
  for (final caso in [
    ('CUENTA_NO_ACTIVE', 'La cuenta no está activa para cobrar.'),
    ('DEMO_DESTINO_NO_PERMITIDO', 'El destino no está permitido en demo.'),
    ('MODO_CAMBIO', 'Cambió el modo de cobro. Revisa el pedido.'),
    ('ACEPTACION_REQUERIDA', 'Se requiere una aceptación vigente.'),
    ('PROVEEDOR_NO_DISPONIBLE', 'El cobro no está habilitado todavía.'),
    ('PAGO_NO_CONFIRMADO', 'El pago aún no está confirmado.'),
    ('PREPARACION_INVALIDA', 'Primero márcalo listo.'),
  ]) {
    test('${caso.$1} muestra mensaje especifico', () async {
      final dio = Dio();
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (o, h) => h.resolve(
            Response(
              requestOptions: o,
              statusCode: 409,
              data: {'codigo': caso.$1},
            ),
          ),
        ),
      );
      await expectLater(
        PedidoRepository(dio).cobro('abc', {}),
        throwsA(
          isA<PedidoException>().having((e) => e.mensaje, 'mensaje', caso.$2),
        ),
      );
    });
  }
}
