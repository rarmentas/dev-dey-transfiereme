import 'package:flutter_test/flutter_test.dart';
import 'package:dio/dio.dart';
import 'package:cody/features/pedidos/data/pedido_repository.dart';

import '../../support/mock_pedido_api.dart';

void main() {
  for (final caso in [
    (
      403,
      <String, dynamic>{'codigo': 'SESION_TERMINADA'},
      'SESION_TERMINADA',
      'Tu sesión terminó. Vuelve a entrar.',
    ),
    (
      401,
      <String, dynamic>{},
      'SESION_TERMINADA',
      'Tu sesión terminó. Vuelve a entrar.',
    ),
    (
      403,
      <String, dynamic>{'codigo': 'PERMISO_DENEGADO', 'detail': 'otro'},
      'PERMISO_DENEGADO',
      'No tienes permiso para este comercio.',
    ),
    (
      409,
      <String, dynamic>{'codigo': 'CLAVE_REUTILIZADA'},
      'CLAVE_REUTILIZADA',
      'No pudimos guardar. Intenta de nuevo.',
    ),
    (
      503,
      <String, dynamic>{'codigo': 'SERVICIO_NO_DISPONIBLE'},
      'SERVICIO_NO_DISPONIBLE',
      'El servidor no está disponible. Intenta de nuevo.',
    ),
  ]) {
    test('mapea ${caso.$1} ${caso.$3}', () async {
      final mock = MockPedidoApi(crearDioPedido());
      mock.responder('GET', '/api/pedidos/', caso.$1, caso.$2);
      expect(
        () => PedidoRepository(mock.dio).listar(),
        throwsA(
          isA<PedidoException>()
              .having((e) => e.codigo, 'codigo', caso.$3)
              .having((e) => e.mensaje, 'mensaje', caso.$4),
        ),
      );
    });
  }
  test('M5 403 CSRF sin código muestra error genérico', () async {
    final mock = MockPedidoApi(crearDioPedido());
    mock.responder('GET', '/api/pedidos/', 403, {
      'detail': 'CSRF Failed: token missing.',
    });
    await expectLater(
      PedidoRepository(mock.dio).listar(),
      throwsA(
        isA<PedidoException>()
            .having((e) => e.codigo, 'codigo', 'ERROR')
            .having(
              (e) => e.mensaje,
              'mensaje',
              'No pudimos completar la solicitud. Intenta de nuevo.',
            ),
      ),
    );
  });
  test('M5 403 sin detail ni código muestra error genérico', () async {
    final mock = MockPedidoApi(crearDioPedido());
    mock.responder('GET', '/api/pedidos/', 403, {});
    await expectLater(
      PedidoRepository(mock.dio).listar(),
      throwsA(
        isA<PedidoException>()
            .having((e) => e.codigo, 'codigo', 'ERROR')
            .having(
              (e) => e.mensaje,
              'mensaje',
              'No pudimos completar la solicitud. Intenta de nuevo.',
            ),
      ),
    );
  });
  test('lee lista vacía y ruta', () async {
    final mock = MockPedidoApi(crearDioPedido());
    mock.responder('GET', '/api/pedidos/', 200, exito({'pedidos': []}));
    expect(await PedidoRepository(mock.dio).listar(), isEmpty);
    expect(mock.peticiones.single.path, '/api/pedidos/');
  });
  test('falla de conexión se mapea sin usar texto del servidor', () async {
    final dio = crearDioPedido();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (opciones, handler) {
          handler.reject(
            DioException(
              requestOptions: opciones,
              type: DioExceptionType.connectionError,
            ),
          );
        },
      ),
    );
    await expectLater(
      PedidoRepository(dio).listar(),
      throwsA(
        isA<PedidoException>()
            .having((e) => e.codigo, 'codigo', 'RED')
            .having(
              (e) => e.mensaje,
              'mensaje',
              'No pudimos conectar. Revisa tu conexión e intenta de nuevo.',
            ),
      ),
    );
  });
  test('envía los renglones sin totales al endpoint correcto', () async {
    final mock = MockPedidoApi(crearDioPedido());
    mock.responder(
      'PUT',
      '/api/pedidos/abc/renglones/',
      200,
      exito(pedidoJson()),
    );
    final cuerpo = {
      'command_key': 'clave',
      'expected_version': 1,
      'renglones': [
        {'renglon_id': 'r1', 'cantidad': '1', 'precio_unitario_centavos': 1250},
      ],
    };
    final pedido = await PedidoRepository(mock.dio).revisar('abc', cuerpo);
    expect(pedido.numero, 7);
    expect(mock.peticiones.single.metodo, 'PUT');
    expect(mock.peticiones.single.cuerpo, cuerpo);
    expect(mock.peticiones.single.cuerpo.toString(), isNot(contains('total')));
  });
}
