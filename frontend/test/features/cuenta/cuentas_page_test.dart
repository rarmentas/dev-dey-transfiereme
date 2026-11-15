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

  testWidgets(
    'I3 dos cuentas muestran estado y resultado de sincronizacion propios',
    (t) async {
      final dio = Dio(BaseOptions(baseUrl: 'http://test'));
      final adapter = DioAdapter(dio: dio);
      var sincronizada = false;
      Map<String, dynamic> datos(String id) => {
        'id': id,
        'clabe_enmascarada': id == '1' ? '••••1234' : '••••5678',
        'registro_estado': 'registrado',
        'codi_status': 'active',
        'puede_cobrar': true,
        'version': 1,
        'sincronizada_en': id == '1'
            ? '2026-01-02T12:30:00Z'
            : '2026-02-03T14:45:00Z',
        'ultimo_error': id == '1'
            ? (sincronizada ? 'TimeoutPey req-1' : '')
            : 'ErrorPey req-2',
        'anomalia': id == '1' ? '' : 'CLABE_NO_COINCIDE',
        'operacion': id == '1'
            ? {'tipo': 'sync', 'estado': 'en_curso'}
            : {'tipo': 'registro', 'estado': 'aplicada'},
      };
      adapter.onGet(
        '/api/cuenta/cuentas/',
        (s) => s.replyCallback(
          200,
          (_) => {
            'cuentas': [datos('1'), datos('2')],
          },
        ),
      );
      adapter.onPost(
        '/api/cuenta/cuentas/1/sincronizar/',
        (s) => s.replyCallback(200, (_) {
          sincronizada = true;
          return {'cuenta': datos('1')};
        }),
        data: {},
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
      final tarjeta1 = find.ancestor(
        of: find.text('••••1234'),
        matching: find.byType(Card),
      );
      final tarjeta2 = find.ancestor(
        of: find.text('••••5678'),
        matching: find.byType(Card),
      );
      expect(
        find.descendant(
          of: tarjeta1,
          matching: find.textContaining('2026-01-02'),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: tarjeta2,
          matching: find.textContaining('2026-02-03'),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: tarjeta2,
          matching: find.textContaining('ErrorPey req-2'),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: tarjeta2,
          matching: find.textContaining('CLABE_NO_COINCIDE'),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: tarjeta1,
          matching: find.textContaining('Sincronización en curso'),
        ),
        findsOneWidget,
      );
      await t.tap(
        find.descendant(of: tarjeta1, matching: find.text('Sincronizar')),
      );
      await t.pumpAndSettle();
      expect(
        find.descendant(of: tarjeta1, matching: find.textContaining('Activa')),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: tarjeta1,
          matching: find.textContaining('TimeoutPey req-1'),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: tarjeta1,
          matching: find.textContaining('2026-01-02'),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: tarjeta2,
          matching: find.textContaining('ErrorPey req-2'),
        ),
        findsOneWidget,
      );
      expect(find.textContaining('000000000000001234'), findsNothing);
    },
  );

  testWidgets('I3 operación pendiente se distingue de en curso', (t) async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test'));
    final adapter = DioAdapter(dio: dio);
    adapter.onGet(
      '/api/cuenta/cuentas/',
      (s) => s.reply(200, {
        'cuentas': [
          {
            'id': '1',
            'clabe_enmascarada': '••••1234',
            'version': 1,
            'operacion': {'tipo': 'sync', 'estado': 'pendiente'},
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
    expect(find.text('Sincronización pendiente'), findsOneWidget);
    expect(find.text('Sincronización en curso'), findsNothing);
    expect(find.text('Última sincronización: sin datos'), findsOneWidget);
  });

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
