import 'package:dio/dio.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';

const estadoCuentaPruebaPaso1 = {
  'fase': 'sin_clabe',
  'paso': 1,
  'codi_status': 'pending',
  'puede_cobrar': false,
  'clabe_enmascarada': '',
  'tiene_cuenta_pey': false,
  'pey_bank_account_id_sufijo': '',
  'actualizado_en': null,
};

void instalarCuentaEstadoApi(
  Dio dio, {
  Map<String, dynamic> estado = estadoCuentaPruebaPaso1,
}) {
  final adapter = DioAdapter(dio: dio);
  adapter.onGet(
    '/api/cuenta/pey/estado/',
    (server) => server.reply(200, estado),
  );
}
