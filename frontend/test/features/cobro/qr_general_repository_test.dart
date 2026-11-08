import 'package:cody/core/network/providers.dart';
import 'package:cody/features/cobro/data/qr_general_repository.dart';
import 'package:cody/features/cobro/presentation/mi_qr_page.dart';
import 'package:cody/features/cobro/presentation/qr_general_impreso_page.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';

Dio _dio() => Dio(
  BaseOptions(
    baseUrl: 'http://test',
    validateStatus: (status) => status != null && status < 500,
  ),
);

DioAdapter _responder(Dio dio, int status, Map<String, dynamic> cuerpo) {
  final adapter = DioAdapter(dio: dio);
  adapter.onPost(
    QrGeneralRepository.ruta,
    (server) => server.reply(status, cuerpo),
    data: <String, dynamic>{},
  );
  return adapter;
}

void main() {
  group('QrGeneralRepository', () {
    test('201 devuelve el qr_string', () async {
      final dio = _dio();
      _responder(dio, 201, {'qr_string': 'cody://qr/1', 'pey_qr_id': 'x'});
      final r = await QrGeneralRepository(dio).obtener();
      expect(r.cuentaNoActiva, isFalse);
      expect(r.qrString, 'cody://qr/1');
    });

    test('200 devuelve el qr_string', () async {
      final dio = _dio();
      _responder(dio, 200, {'qr_string': 'cody://qr/2'});
      final r = await QrGeneralRepository(dio).obtener();
      expect(r.qrString, 'cody://qr/2');
    });

    test('400 INVALID_STATE es cuenta no activa', () async {
      final dio = _dio();
      _responder(dio, 400, {'detail': 'x', 'tipo': 'INVALID_STATE'});
      final r = await QrGeneralRepository(dio).obtener();
      expect(r.cuentaNoActiva, isTrue);
      expect(r.qrString, isNull);
    });

    test('403 lanza con el detalle', () async {
      final dio = _dio();
      _responder(dio, 403, {'detail': 'Sin permiso.'});
      expect(
        QrGeneralRepository(dio).obtener(),
        throwsA(
          isA<QrGeneralApiException>().having(
            (e) => e.mensaje,
            'mensaje',
            'Sin permiso.',
          ),
        ),
      );
    });

    test('respuesta sin qr_string lanza', () async {
      final dio = _dio();
      _responder(dio, 200, {});
      expect(
        QrGeneralRepository(dio).obtener(),
        throwsA(isA<QrGeneralApiException>()),
      );
    });
  });

  group('MiQrPage', () {
    Future<void> montar(WidgetTester tester, Dio dio) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [dioProvider.overrideWithValue(dio)],
          child: MaterialApp(theme: TfTheme.light, home: const MiQrPage()),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
    }

    testWidgets('muestra el QR', (tester) async {
      final dio = _dio();
      _responder(dio, 200, {'qr_string': 'cody://qr/3'});
      await montar(tester, dio);
      expect(find.byType(QrGeneralImpresoPage), findsOneWidget);
      expect(find.textContaining('Tu cliente puede pagar'), findsOneWidget);
      expect(find.byTooltip('Volver'), findsOneWidget);
    });

    testWidgets('cuenta no activa muestra el aviso', (tester) async {
      final dio = _dio();
      _responder(dio, 400, {'detail': 'x', 'tipo': 'INVALID_STATE'});
      await montar(tester, dio);
      expect(find.text(kMensajeCuentaNoActivaQr), findsOneWidget);
      expect(find.text(kMensajeQrAlActivar), findsOneWidget);
      expect(find.byTooltip('Volver'), findsOneWidget);
    });

    testWidgets('error ofrece Reintentar', (tester) async {
      final dio = _dio();
      _responder(dio, 403, {'detail': 'Sin permiso.'});
      await montar(tester, dio);
      expect(find.text('Reintentar'), findsOneWidget);
      expect(find.text('Sin permiso.'), findsOneWidget);
      expect(find.byTooltip('Volver'), findsOneWidget);
    });
  });
}
