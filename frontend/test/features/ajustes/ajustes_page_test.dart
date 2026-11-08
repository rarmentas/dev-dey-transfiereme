import 'package:cody/core/router/app_router.dart';
import 'package:cody/core/sesion/sesion_models.dart';
import 'package:cody/core/sesion/sesion_notifier.dart';
import 'package:cody/core/sesion/sesion_view_state.dart';
import 'package:cody/features/ajustes/data/comercio_repository.dart';
import 'package:cody/features/ajustes/presentation/ajustes_page.dart';
import 'package:cody/features/ajustes/presentation/ajustes_providers.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

class _RepoNombreFalso extends ComercioRepository {
  _RepoNombreFalso() : super(Dio(BaseOptions(baseUrl: 'http://test')));

  var llamadas = 0;
  ComercioActualizado? resultado;
  Object? error;

  @override
  Future<ComercioActualizado> actualizarNombre(String nombre) async {
    llamadas++;
    if (error != null) {
      throw error!;
    }
    return resultado ??
        ComercioActualizado(id: 1, nombre: nombre.trim());
  }
}

class _SesionSinNombre extends SesionNotifier {
  @override
  SesionViewState build() => const SesionViewState(
    resuelto: true,
    cargando: false,
    estado: EstadoSesion(
      usuario: 'demo',
      correo: 'demo@cody.mx',
      nombre: '',
      apellidos: '',
      comercio: ComercioResumen(id: 1, nombre: 'Abarrotes Demo'),
    ),
  );
}

class _SesionFija extends SesionNotifier {
  @override
  SesionViewState build() => const SesionViewState(
    resuelto: true,
    cargando: false,
    estado: EstadoSesion(
      usuario: 'lupe',
      correo: 'lupe@tortilleria.mx',
      nombre: 'Lupe',
      apellidos: 'García',
      comercio: ComercioResumen(id: 1, nombre: 'Tortillería La Esperanza'),
    ),
  );
}

void main() {
  testWidgets('muestra datos de la cuenta y navega a Mi QR', (tester) async {
    final router = GoRouter(
      initialLocation: kRutaAjustes,
      routes: [
        GoRoute(
          path: kRutaAjustes,
          builder: (context, state) => const AjustesPage(),
        ),
        GoRoute(
          path: kRutaMiQr,
          builder: (context, state) => const Scaffold(body: Text('destino qr')),
        ),
      ],
    );
    addTearDown(router.dispose);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [sesionNotifierProvider.overrideWith(_SesionFija.new)],
        child: MaterialApp.router(theme: TfTheme.light, routerConfig: router),
      ),
    );
    await tester.pump();

    expect(find.text('Ajustes'), findsOneWidget);
    expect(find.text('Lupe García'), findsOneWidget);
    expect(find.text('lupe@tortilleria.mx'), findsOneWidget);
    final correo = tester.widget<Text>(find.text('lupe@tortilleria.mx'));
    expect(correo.style?.color, TfTheme.light.colorScheme.onSurfaceVariant);
    expect(find.text('Mi comercio'), findsOneWidget);
    expect(find.text('Tortillería La Esperanza'), findsOneWidget);
    expect(find.byKey(const Key('boton_editar_nombre_comercio')), findsOneWidget);
    expect(find.text('Salir'), findsOneWidget);
    final salir = tester.widget<OutlinedButton>(
      find.byKey(const Key('boton_salir')),
    );
    expect(
      salir.style?.foregroundColor?.resolve(<WidgetState>{}),
      TfTheme.light.colorScheme.onSurfaceVariant,
    );
    expect(
      salir.style?.side?.resolve(<WidgetState>{})?.color,
      TfTheme.light.colorScheme.outlineVariant,
    );
    expect(
      tester.getSize(find.byKey(const Key('boton_salir'))).height,
      greaterThanOrEqualTo(48),
    );
    expect(
      tester.getSize(find.byType(Card).first).width,
      lessThanOrEqualTo(480),
    );

    await tester.tap(find.byKey(const Key('opcion_mi_qr')));
    await tester.pumpAndSettle();
    expect(find.text('destino qr'), findsOneWidget);
  });

  testWidgets('sin nombre el correo es un dato y no el título', (tester) async {
    final router = GoRouter(
      initialLocation: kRutaAjustes,
      routes: [
        GoRoute(
          path: kRutaAjustes,
          builder: (context, state) => const AjustesPage(),
        ),
      ],
    );
    addTearDown(router.dispose);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [sesionNotifierProvider.overrideWith(_SesionSinNombre.new)],
        child: MaterialApp.router(theme: TfTheme.light, routerConfig: router),
      ),
    );
    await tester.pump();

    final correo = tester.widget<Text>(find.text('demo@cody.mx'));
    expect(correo.style?.color, TfTheme.light.colorScheme.onSurfaceVariant);
    expect(
      correo.style?.fontSize,
      TfTheme.light.textTheme.bodyMedium?.fontSize,
    );
    expect(correo.style?.fontWeight, FontWeight.w400);
    expect(find.text('Abarrotes Demo'), findsOneWidget);
  });

  testWidgets('guardar nombre actualiza la tarjeta', (tester) async {
    final repo = _RepoNombreFalso()
      ..resultado = const ComercioActualizado(
        id: 1,
        nombre: 'Abarrotes del Centro',
      );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sesionNotifierProvider.overrideWith(_SesionFija.new),
          comercioRepositoryProvider.overrideWithValue(repo),
        ],
        child: MaterialApp(theme: TfTheme.light, home: const AjustesPage()),
      ),
    );
    await tester.pump();
    await tester.tap(find.byKey(const Key('boton_editar_nombre_comercio')));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const Key('campo_nombre_comercio')),
      '  Abarrotes del Centro  ',
    );
    await tester.tap(find.byKey(const Key('boton_guardar_nombre_comercio')));
    await tester.pumpAndSettle();

    expect(repo.llamadas, 1);
    expect(find.byType(AlertDialog), findsNothing);
    expect(find.text('Abarrotes del Centro'), findsOneWidget);
  });

  testWidgets('tras PATCH actualiza comercio en la sesión local', (tester) async {
    final repo = _RepoNombreFalso()
      ..resultado = const ComercioActualizado(id: 1, nombre: 'Nuevo local');
    late ProviderContainer container;
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sesionNotifierProvider.overrideWith(_SesionFija.new),
          comercioRepositoryProvider.overrideWithValue(repo),
        ],
        child: MaterialApp(
          theme: TfTheme.light,
          home: Builder(
            builder: (context) {
              container = ProviderScope.containerOf(context);
              return const AjustesPage();
            },
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.tap(find.byKey(const Key('boton_editar_nombre_comercio')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('boton_guardar_nombre_comercio')));
    await tester.pumpAndSettle();

    expect(repo.llamadas, 1);
    expect(
      container.read(sesionNotifierProvider).estado?.comercio?.nombre,
      'Nuevo local',
    );
  });

  testWidgets('doble guardar nombre envía un solo PATCH', (tester) async {
    final repo = _RepoNombreFalso()
      ..resultado = const ComercioActualizado(id: 1, nombre: 'Uno');
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sesionNotifierProvider.overrideWith(_SesionFija.new),
          comercioRepositoryProvider.overrideWithValue(repo),
        ],
        child: MaterialApp(theme: TfTheme.light, home: const AjustesPage()),
      ),
    );
    await tester.pump();
    await tester.tap(find.byKey(const Key('boton_editar_nombre_comercio')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('boton_guardar_nombre_comercio')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('boton_guardar_nombre_comercio')));
    await tester.pumpAndSettle();
    expect(repo.llamadas, 1);
  });

  testWidgets('nombre de 200 caracteres es válido en el formulario', (
    tester,
  ) async {
    final repo = _RepoNombreFalso();
    final largo = 'a' * 200;
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sesionNotifierProvider.overrideWith(_SesionFija.new),
          comercioRepositoryProvider.overrideWithValue(repo),
        ],
        child: MaterialApp(theme: TfTheme.light, home: const AjustesPage()),
      ),
    );
    await tester.pump();
    await tester.tap(find.byKey(const Key('boton_editar_nombre_comercio')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('campo_nombre_comercio')), largo);
    await tester.tap(find.byKey(const Key('boton_guardar_nombre_comercio')));
    await tester.pumpAndSettle();
    expect(repo.llamadas, 1);
    expect(find.text('Tortillería La Esperanza'), findsNothing);
    expect(find.text(largo), findsOneWidget);
  });

  testWidgets('cancelar no guarda el nombre', (tester) async {
    final repo = _RepoNombreFalso();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sesionNotifierProvider.overrideWith(_SesionFija.new),
          comercioRepositoryProvider.overrideWithValue(repo),
        ],
        child: MaterialApp(theme: TfTheme.light, home: const AjustesPage()),
      ),
    );
    await tester.pump();
    await tester.tap(find.byKey(const Key('boton_editar_nombre_comercio')));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const Key('campo_nombre_comercio')),
      'Otro nombre',
    );
    await tester.tap(find.byKey(const Key('boton_cancelar_nombre_comercio')));
    await tester.pumpAndSettle();

    expect(repo.llamadas, 0);
    expect(find.text('Tortillería La Esperanza'), findsOneWidget);
  });

  testWidgets('nombre vacío no llama al servidor', (tester) async {
    final repo = _RepoNombreFalso();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sesionNotifierProvider.overrideWith(_SesionFija.new),
          comercioRepositoryProvider.overrideWithValue(repo),
        ],
        child: MaterialApp(theme: TfTheme.light, home: const AjustesPage()),
      ),
    );
    await tester.pump();
    await tester.tap(find.byKey(const Key('boton_editar_nombre_comercio')));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('campo_nombre_comercio')), '   ');
    await tester.tap(find.byKey(const Key('boton_guardar_nombre_comercio')));
    await tester.pump();

    expect(find.text('Indique el nombre del comercio.'), findsOneWidget);
    expect(repo.llamadas, 0);
  });

  testWidgets('error del servidor se muestra sin cerrar', (tester) async {
    final repo = _RepoNombreFalso()
      ..error = ComercioApiException('No pudimos guardar el nombre.');
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sesionNotifierProvider.overrideWith(_SesionFija.new),
          comercioRepositoryProvider.overrideWithValue(repo),
        ],
        child: MaterialApp(theme: TfTheme.light, home: const AjustesPage()),
      ),
    );
    await tester.pump();
    await tester.tap(find.byKey(const Key('boton_editar_nombre_comercio')));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('boton_guardar_nombre_comercio')));
    await tester.pumpAndSettle();

    expect(find.text('No pudimos guardar el nombre.'), findsOneWidget);
    expect(find.byType(AlertDialog), findsOneWidget);
    expect(repo.llamadas, 1);
  });
}
