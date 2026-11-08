import 'package:cody/core/router/app_router.dart';
import 'package:cody/core/sesion/sesion_models.dart';
import 'package:cody/core/sesion/sesion_notifier.dart';
import 'package:cody/core/sesion/sesion_view_state.dart';
import 'package:cody/features/cuenta/data/clabe_repository.dart';
import 'package:cody/features/cuenta/presentation/registrar_clabe_page.dart';
import 'package:cody/features/ajustes/presentation/ajustes_page.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'dart:async';

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
          final metodo = options.method.toUpperCase();
          if (metodo == 'GET') {
            llamadasGet++;
          } else if (metodo == 'POST') {
            llamadasPost++;
          }
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
  var llamadasGet = 0;
  var llamadasPost = 0;

  void alGuardar(int status, Map<String, dynamic> cuerpo) {
    adapter.onPost(
      ClabeRepository.ruta,
      (server) => server.reply(status, cuerpo),
      data: Matchers.any,
    );
  }

  void alObtener(int status, Map<String, dynamic> cuerpo) {
    adapter.onGet(
      ClabeRepository.ruta,
      (server) => server.reply(status, cuerpo),
    );
  }

}

class _RepoClabeLento extends ClabeRepository {
  _RepoClabeLento(this._clabeInicial)
      : super(Dio(BaseOptions(baseUrl: 'http://test')));

  final String _clabeInicial;

  @override
  Future<String> obtener() async {
    await Future<void>.delayed(const Duration(milliseconds: 300));
    return _clabeInicial;
  }

  @override
  Future<String> guardar(String clabe) async => clabe;
}

class _RepoGetPendienteTrasPost extends ClabeRepository {
  _RepoGetPendienteTrasPost() : super(Dio(BaseOptions(baseUrl: 'http://test')));

  final _obtener = Completer<String>();

  void completarObtener(String clabe) {
    if (!_obtener.isCompleted) {
      _obtener.complete(clabe);
    }
  }

  @override
  Future<String> obtener() => _obtener.future;

  @override
  Future<String> guardar(String clabe) async => clabe;
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
  testWidgets('Ajustes abre Registrar CLABE', (tester) async {
    final router = GoRouter(
      initialLocation: kRutaAjustes,
      routes: [
        GoRoute(
          path: kRutaAjustes,
          builder: (context, state) => const AjustesPage(),
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

  testWidgets('al abrir solo llama GET y no POST', (tester) async {
    final dio = _dio();
    final mock = _MockClabe(dio);
    mock.alObtener(200, {'clabe': ''});
    await _montarPagina(tester, ClabeRepository(dio));
    await tester.pumpAndSettle();
    expect(mock.llamadasGet, 1);
    expect(mock.llamadasPost, 0);
  });

  testWidgets('guardar actualiza el bloque CLABE actual', (tester) async {
    const anterior = '646180157000123456';
    const nueva = '012180015826225713';
    final dio = _dio();
    final mock = _MockClabe(dio);
    mock.alObtener(200, {'clabe': anterior});
    mock.alGuardar(200, {'clabe': nueva});
    await _montarPagina(tester, ClabeRepository(dio));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('campo_clabe')), nueva);
    await tester.tap(find.byKey(const Key('boton_guardar_clabe')));
    await tester.pumpAndSettle();

    final actual = tester.widget<Text>(find.byKey(const Key('texto_clabe_actual')));
    expect(actual.data, nueva);
    expect(find.text(anterior), findsNothing);
  });

  testWidgets('GET que llega tras POST no revierte la CLABE guardada', (
    tester,
  ) async {
    const anterior = '646180157000123456';
    const nueva = '012180015826225713';
    final repo = _RepoGetPendienteTrasPost();
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          theme: TfTheme.light,
          home: RegistrarClabePage(repositorio: repo),
        ),
      ),
    );
    await tester.pump();
    await tester.enterText(find.byKey(const Key('campo_clabe')), nueva);
    await tester.tap(find.byKey(const Key('boton_guardar_clabe')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    repo.completarObtener(anterior);
    await tester.pumpAndSettle();

    final actual = tester.widget<Text>(find.byKey(const Key('texto_clabe_actual')));
    expect(actual.data, nueva);
    expect(
      tester.widget<TextFormField>(find.byKey(const Key('campo_clabe'))).controller
          ?.text,
      nueva,
    );
    expect(find.text(anterior), findsNothing);
  });

  testWidgets('GET lento no pisa texto que el usuario ya escribió', (
    tester,
  ) async {
    const delServidor = '646180157000123456';
    const escrita = '012180015826225713';
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          theme: TfTheme.light,
          home: RegistrarClabePage(
            repositorio: _RepoClabeLento(delServidor),
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.enterText(find.byKey(const Key('campo_clabe')), escrita);
    await tester.pumpAndSettle(const Duration(milliseconds: 400));
    expect(
      tester.widget<TextFormField>(find.byKey(const Key('campo_clabe'))).controller
          ?.text,
      escrita,
    );
    expect(find.text(delServidor), findsNothing);
  });

  testWidgets('muestra CLABE actual cuando el servidor la devuelve', (
    tester,
  ) async {
    const clabeFicticia = '646180157000123456';
    final dio = _dio();
    final mock = _MockClabe(dio);
    mock.alObtener(200, {'clabe': clabeFicticia});
    mock.alGuardar(200, {'clabe': clabeFicticia});
    await _montarPagina(tester, ClabeRepository(dio));
    await tester.pumpAndSettle();

    expect(find.text('CLABE actual'), findsOneWidget);
    expect(find.byKey(const Key('texto_clabe_actual')), findsOneWidget);
    expect(find.text(clabeFicticia), findsWidgets);
  });

  testWidgets('sin CLABE guardada el bloque actual no aparece', (
    tester,
  ) async {
    final dio = _dio();
    final mock = _MockClabe(dio);
    mock.alObtener(200, {'clabe': ''});
    mock.alGuardar(200, {'clabe': _clabeValida});
    await _montarPagina(tester, ClabeRepository(dio));
    await tester.pumpAndSettle();

    expect(find.text('CLABE actual'), findsNothing);
    expect(find.byKey(const Key('texto_clabe_actual')), findsNothing);
  });

  testWidgets('error al cargar CLABE se muestra sin bloque actual', (
    tester,
  ) async {
    final dio = _dio();
    final mock = _MockClabe(dio);
    mock.alObtener(500, {'detail': 'fallo'});
    await _montarPagina(tester, ClabeRepository(dio));
    await tester.pumpAndSettle();

    expect(find.text('CLABE actual'), findsNothing);
    expect(find.text('fallo'), findsOneWidget);
  });

  testWidgets('una CLABE inválida no llama al servidor', (tester) async {
    final dio = _dio();
    final mock = _MockClabe(dio);
    mock.alObtener(200, {'clabe': ''});
    mock.alGuardar(200, {'clabe': _clabeValida});
    await _montarPagina(tester, ClabeRepository(dio));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('campo_clabe')), '123');
    await tester.tap(find.byKey(const Key('boton_guardar_clabe')));
    await tester.pump();

    expect(
      find.text('Escribe una CLABE válida de 18 dígitos.'),
      findsOneWidget,
    );
    expect(mock.cuerpos, isEmpty);
  });

  testWidgets('guardar una CLABE válida muestra la confirmación', (
    tester,
  ) async {
    final dio = _dio();
    final mock = _MockClabe(dio);
    mock.alObtener(200, {'clabe': ''});
    mock.alGuardar(200, {'clabe': _clabeValida});
    await _montarPagina(tester, ClabeRepository(dio));
    await tester.pumpAndSettle();

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
    mock.alObtener(200, {'clabe': ''});
    mock.alGuardar(400, {
      'detail': 'Escribe una CLABE válida de 18 dígitos.',
    });
    await _montarPagina(tester, ClabeRepository(dio));

    await tester.enterText(find.byKey(const Key('campo_clabe')), _clabeValida);
    await tester.tap(find.byKey(const Key('boton_guardar_clabe')));
    await tester.pumpAndSettle();

    expect(
      find.text('Escribe una CLABE válida de 18 dígitos.'),
      findsOneWidget,
    );
    expect(find.text('CLABE guardada.'), findsNothing);
  });
}
