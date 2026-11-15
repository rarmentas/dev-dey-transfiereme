import 'package:cody/core/network/providers.dart';
import 'package:cody/core/router/app_router.dart';
import 'package:cody/core/sesion/sesion_providers.dart';
import 'package:cody/core/sesion/sesion_repository.dart';
import 'package:cody/features/pedidos/data/pedido.dart';
import 'package:cody/features/pedidos/data/pedido_repository.dart';
import 'package:cody/features/pedidos/presentation/catalogo_page.dart';
import 'package:cody/features/pedidos/presentation/pedido_providers.dart';
import 'package:cody/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

import '../../support/mock_inicio_api.dart';
import '../../support/mock_pedido_api.dart';
import '../../support/mock_sesion_api.dart';

class _CatalogoRepo extends PedidoRepository {
  _CatalogoRepo() : super(crearDioPedido());

  @override
  Future<List<PedidoResumen>> listar() async => [];

  @override
  Future<Map<String, dynamic>> catalogo() async => {
    'agente_habilitado': false,
    'es_dueno': true,
    'productos': [
      {
        'id': 1,
        'nombre': 'Tortillas',
        'alias': <String>[],
        'unidad': 'kg',
        'precio_centavos': 2500,
        'disponible': true,
      },
    ],
  };
}

Future<(ProviderContainer, GoRouter)> _abrir(
  WidgetTester tester,
  String ruta, {
  bool autenticado = true,
}) async {
  final dio = crearDioPrueba();
  prepararDioConSesion(dio).autenticado = autenticado;
  instalarInicioApi(dio);
  final container = ProviderContainer(
    overrides: [
      dioProvider.overrideWithValue(dio),
      sesionRepositoryProvider.overrideWith((ref) => SesionRepository(dio)),
      pedidoRepositoryProvider.overrideWithValue(_CatalogoRepo()),
    ],
  );
  final router = container.read(routerProvider);
  router.go(ruta);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: const TransfieremeApp(),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 400));
  await tester.pumpAndSettle();
  return (container, router);
}

Future<void> _cerrar(WidgetTester tester, ProviderContainer container) async {
  await tester.pumpWidget(const SizedBox.shrink());
  container.dispose();
}

void main() {
  testWidgets('el quinto destino abre y selecciona Catálogo', (tester) async {
    final (container, router) = await _abrir(tester, kRutaInicio);
    final barra = tester.widget<NavigationBar>(find.byType(NavigationBar));
    expect(barra.destinations, hasLength(5));
    expect(barra.selectedIndex, 0);
    await tester.tap(find.text('Catálogo'));
    await tester.pumpAndSettle();
    expect(find.byType(CatalogoPage), findsOneWidget);
    expect(find.text('Lista de precios'), findsOneWidget);
    expect(find.text('Tortillas'), findsOneWidget);
    expect(
      tester.widget<NavigationBar>(find.byType(NavigationBar)).selectedIndex,
      4,
    );
    expect(router.routeInformationProvider.value.uri.path, kRutaCatalogo);
    await _cerrar(tester, container);
  });

  testWidgets('la URL directa abre Catálogo con sesión', (tester) async {
    final (container, router) = await _abrir(tester, kRutaCatalogo);
    expect(find.byType(CatalogoPage), findsOneWidget);
    expect(
      tester.widget<NavigationBar>(find.byType(NavigationBar)).selectedIndex,
      4,
    );
    expect(router.routeInformationProvider.value.uri.path, kRutaCatalogo);
    await _cerrar(tester, container);
  });

  testWidgets('la URL directa exige sesión', (tester) async {
    final (container, router) = await _abrir(
      tester,
      kRutaCatalogo,
      autenticado: false,
    );
    expect(find.text('Entra a cobrar'), findsOneWidget);
    expect(find.byType(CatalogoPage), findsNothing);
    expect(router.routeInformationProvider.value.uri.path, kRutaEntrar);
    await _cerrar(tester, container);
  });

  testWidgets('el acceso desde Pedidos abre Catálogo', (tester) async {
    final (container, _) = await _abrir(tester, kRutaPedidos);
    await tester.tap(find.byTooltip('Lista de precios'));
    await tester.pumpAndSettle();
    expect(find.byType(CatalogoPage), findsOneWidget);
    expect(
      tester.widget<NavigationBar>(find.byType(NavigationBar)).selectedIndex,
      4,
    );
    await _cerrar(tester, container);
  });
}
