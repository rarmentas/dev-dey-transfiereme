import 'package:cody/features/cuenta/data/cuentas_repository.dart';
import 'package:cody/features/cuenta/data/clabe_repository.dart';
import 'package:cody/features/cuenta/data/cuenta_estado_repository.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';

void main() {
  test('lectores anteriores tambien ocultan CLABE completa', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test'));
    final adapter = DioAdapter(dio: dio);
    adapter.onGet(
      '/api/cuenta/clabe/',
      (s) => s.reply(200, {'clabe': '000000000000001234'}),
    );
    adapter.onGet(
      '/api/cuenta/pey/estado/',
      (s) => s.reply(200, {'clabe_enmascarada': '000000000000001234'}),
    );
    expect(await ClabeRepository(dio).obtener(), '••••1234');
    expect(
      (await CuentaEstadoRepository(dio).obtenerEstado()).clabeEnmascarada,
      '••••1234',
    );
  });

  test('alta agrega cuenta y conserva solo CLABE enmascarada', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test'));
    final adapter = DioAdapter(dio: dio);
    adapter.onPost(
      '/api/cuenta/cuentas/',
      (s) => s.reply(201, {
        'cuenta': {
          'id': '1',
          'clabe_enmascarada': '012345678901234567',
          'version': 1,
        },
      }),
      data: {'clabe': '012345678901234567'},
    );
    final cuenta = await CuentasRepository(dio).crear('012345678901234567');
    expect(cuenta.id, '1');
    expect(cuenta.clabe, '••••4567');
  });

  test('error se identifica por codigo y no por detalle', () async {
    final dio = Dio(
      BaseOptions(baseUrl: 'http://test', validateStatus: (_) => true),
    );
    final adapter = DioAdapter(dio: dio);
    adapter.onPost(
      '/api/cuenta/cuentas/',
      (s) =>
          s.reply(409, {'codigo': 'CLABE_DUPLICADA', 'detail': 'otro texto'}),
      data: {'clabe': '123'},
    );
    expect(
      () => CuentasRepository(dio).crear('123'),
      throwsA(
        isA<CuentasException>()
            .having((e) => e.codigo, 'codigo', 'CLABE_DUPLICADA')
            .having((e) => e.mensaje, 'mensaje', 'Ya está guardada.'),
      ),
    );
  });
}
