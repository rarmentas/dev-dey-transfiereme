import 'package:cody/core/router/app_router.dart';
import 'package:cody/core/sesion/sesion_models.dart';
import 'package:cody/core/sesion/sesion_notifier.dart';
import 'package:cody/core/sesion/sesion_view_state.dart';
import 'package:cody/features/cuenta/data/clabe_repository.dart';
import 'package:cody/features/cuenta/presentation/registrar_clabe_page.dart';
import 'package:cody/features/sesion/presentation/home_autenticado_page.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:http_mock_adapter/http_mock_adapter.dart';

const _clabeValida = '012180015826225713';

Dio _dio() {
  return Dio(
    BaseOptions(
      baseUrl: 'http://test',
      headers: const {'Accept': 'application/json'},
      validateStatus: (status) => status != null && status < 500,
    ),
  );
}

class _MockClabe {
  _MockClabe(this.dio) : adapter = DioAdapter(dio: dio) {
    dio.interceptors.insert(
      0,
      InterceptorsWrapper(
        onRequest: (options, handler) {
          final data = options.data;
          if (data is Map<String, dynamic>) {
            cuerpos.add(Map<String, dynamic>.from(data));
          }
          handler.next(options);
        },
      ),
    );
  }

  final Dio dio;
  final DioAdapter adapter;
  final List<Map<String, dynamic>> cuerpos = [];

  void alGuardar(int status, Map<String, dynamic> cuerpo) {
    adapter.onPost(
      ClabeRepository.ruta,
      (server) => server.reply(status, cuerpo),
      data: Matchers.any,
    );
  }
}

Future<void> _montarPagina(WidgetTester tester, ClabeRepository repositorio) async {
  final router = GoRouter(
    initialLocation: kRutaRegistrarClabe,
    routes: [
      GoRoute(
        path: kRutaRegistrarClabe,
        builder: (context, state) =>
            RegistrarClabePage(repositorio: repositorio),
      ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      child: MaterialApp.router(theme: TfTheme.light, routerConfig: router),
    ),
  );
  await tester.pump();
}

class _SesionFija extends SesionNotifier {
  @override
  SesionViewState build() {
    return const SesionViewState(
      resuelto: true,
      cargando: false,
      estado: EstadoSesion(
        usuario: 'vendedor',
        correo: 'vendedor@demo.mx',
        nombre: 'Ada',
        apellidos: '',
        comercio: ComercioResumen(id: 1, nombre: 'Comercio demo'),
      ),
    );
  }
}

void main() {
  testWidgets('el inicio abre Registrar CLABE', (tester) async {
    final router = GoRouter(
      initialLocation: kRutaInicio,
      routes: [
        GoRoute(
          path: kRutaInicio,
          builder: (context, state) => const HomeAutenticadoPage(),
        ),
        GoRoute(
          path: kRutaRegistrarClabe,
          builder: (context, state) => const RegistrarClabePage(),
        ),
      ],
    );
    addTearDown(router.dispose);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sesionNotifierProvider.overrideWith(_SesionFija.new),
        ],
        child: MaterialApp.router(theme: TfTheme.light, routerConfig: router),
      ),
    );
    await tester.pump();

    expect(find.text('Registrar CLABE'), findsOneWidget);
    await tester.tap(find.byKey(const Key('boton_registrar_clabe')));
    await tester.pumpAndSettle();

    expect(find.widgetWithText(AppBar, 'Registrar CLABE'), findsOneWidget);
    expect(find.byKey(const Key('campo_clabe')), findsOneWidget);
  });

  testWidgets('una CLABE inválida no llama al servidor', (tester) async {
    final dio = _dio();
    final mock = _MockClabe(dio);
    mock.alGuardar(200, {'clabe': _clabeValida});
    await _montarPagina(tester, ClabeRepository(dio));

    await tester.enterText(find.byKey(const Key('campo_clabe')), '123');
    await tester.tap(find.byKey(const Key('boton_guardar_clabe')));
    await tester.pump();

    expect(
      find.text('Indique una CLABE válida de 18 dígitos.'),
      findsOneWidget,
    );
    expect(mock.cuerpos, isEmpty);
  });

  testWidgets('guardar una CLABE válida muestra la confirmación', (
    tester,
  ) async {
    final dio = _dio();
    final mock = _MockClabe(dio);
    mock.alGuardar(200, {'clabe': _clabeValida});
    await _montarPagina(tester, ClabeRepository(dio));

    await tester.enterText(find.byKey(const Key('campo_clabe')), _clabeValida);
    await tester.tap(find.byKey(const Key('boton_guardar_clabe')));
    await tester.pumpAndSettle();

    expect(find.text('CLABE guardada.'), findsOneWidget);
    expect(find.text(_clabeValida), findsWidgets);
    expect(mock.cuerpos, [
      {'clabe': _clabeValida},
    ]);
  });

  testWidgets('el error del servidor se muestra', (tester) async {
    final dio = _dio();
    final mock = _MockClabe(dio);
    mock.alGuardar(400, {
      'detail': 'Indique una CLABE válida de 18 dígitos.',
    });
    await _montarPagina(tester, ClabeRepository(dio));

    await tester.enterText(find.byKey(const Key('campo_clabe')), _clabeValida);
    await tester.tap(find.byKey(const Key('boton_guardar_clabe')));
    await tester.pumpAndSettle();

    expect(
      find.text('Indique una CLABE válida de 18 dígitos.'),
      findsOneWidget,
    );
    expect(find.text('CLABE guardada.'), findsNothing);
  });
}
