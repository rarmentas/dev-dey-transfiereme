import 'package:cody/features/cuenta/presentation/cuentas_page.dart';
import 'package:cody/features/cuenta/presentation/cuentas_providers.dart';
import 'package:cody/features/cuenta/data/cuentas_repository.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';

void main() {
  testWidgets(
    'lista dos cuentas con estado propio y no repite registro incierto',
    (t) async {
      final dio = Dio(BaseOptions(baseUrl: 'http://test'));
      final adapter = DioAdapter(dio: dio);
      adapter.onGet(
        '/api/cuenta/cuentas/',
        (s) => s.reply(200, {
          'cuentas': [
            {
              'id': '1',
              'clabe_enmascarada': '**************1234',
              'registro_estado': 'incierto',
              'codi_status': 'pending',
              'version': 1,
            },
            {
              'id': '2',
              'clabe_enmascarada': '**************5678',
              'registro_estado': 'registrado',
              'codi_status': 'active',
              'es_predeterminada': true,
              'version': 1,
            },
          ],
        }),
      );
      await t.pumpWidget(
        ProviderScope(
          overrides: [
            cuentasRepositoryProvider.overrideWithValue(CuentasRepository(dio)),
          ],
          child: const MaterialApp(home: CuentasPage()),
        ),
      );
      await t.pumpAndSettle();
      expect(find.text('**************1234'), findsOneWidget);
      expect(find.textContaining('Por defecto'), findsOneWidget);
      expect(find.textContaining('Registro sin confirmar'), findsOneWidget);
      expect(find.widgetWithText(OutlinedButton, 'Registrar'), findsNothing);
      expect(
        find.widgetWithText(OutlinedButton, 'Sincronizar'),
        findsNWidgets(2),
      );
    },
  );

  testWidgets('lista vacia ofrece alta y valida antes de enviar', (t) async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test'));
    final adapter = DioAdapter(dio: dio);
    adapter.onGet('/api/cuenta/cuentas/', (s) => s.reply(200, {'cuentas': []}));
    await t.pumpWidget(
      ProviderScope(
        overrides: [
          cuentasRepositoryProvider.overrideWithValue(CuentasRepository(dio)),
        ],
        child: const MaterialApp(home: CuentasPage()),
      ),
    );
    await t.pumpAndSettle();
    expect(find.text('Aún no tienes cuentas'), findsOneWidget);
    await t.tap(find.text('Agregar cuenta'));
    await t.pump();
    expect(
      find.text('La CLABE debe tener 18 dígitos y ser válida.'),
      findsOneWidget,
    );
  });
}
