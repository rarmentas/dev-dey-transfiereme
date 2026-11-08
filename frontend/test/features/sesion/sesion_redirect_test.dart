import 'package:cody/core/network/providers.dart';
import 'package:cody/core/router/app_router.dart';
import 'package:cody/core/sesion/registro_olvido_repository.dart';
import 'package:cody/core/sesion/sesion_notifier.dart';
import 'package:cody/core/sesion/sesion_providers.dart';
import 'package:cody/core/sesion/sesion_repository.dart';
import 'package:cody/main.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import '../../support/mock_sesion_api.dart';

void main() {
  testWidgets('sin sesión al arranque muestra el login', (tester) async {
    final dio = crearDioPrueba();
    prepararDioConSesion(dio);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          dioProvider.overrideWithValue(dio),
          sesionRepositoryProvider.overrideWith(
            (ref) => SesionRepository(dio),
          ),
        ],
        child: const TransfieremeApp(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.text('Entra a cobrar'), findsOneWidget);
  });

  testWidgets('salir regresa al login', (tester) async {
    final dio = crearDioPrueba();
    final sim = prepararDioConSesion(dio);
    sim.autenticado = true;

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          dioProvider.overrideWithValue(dio),
          sesionRepositoryProvider.overrideWith(
            (ref) => SesionRepository(dio),
          ),
        ],
        child: const TransfieremeApp(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.text('Hola, Lupe'), findsOneWidget);
    await tester.tap(find.text('Salir'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.text('Entra a cobrar'), findsOneWidget);
  });

  testWidgets('sin sesión la ruta registro permanece visible', (tester) async {
    final dio = crearDioPrueba();
    prepararDioConSesion(dio);

    final container = ProviderContainer(
      overrides: [
        dioProvider.overrideWithValue(dio),
        sesionRepositoryProvider.overrideWith(
          (ref) => SesionRepository(dio),
        ),
        registroOlvidoRepositoryProvider.overrideWith(
          (ref) => RegistroOlvidoRepository(dio),
        ),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const TransfieremeApp(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    container.read(routerProvider).go(kRutaRegistro);
    await tester.pumpAndSettle();

    expect(find.text('Enviar código'), findsOneWidget);
    expect(find.text('Entra a cobrar'), findsNothing);
  });

  test('perder sesión al recargar estado lleva a sin autenticación', () async {
    final dio = crearDioPrueba();
    final sim = prepararDioConSesion(dio);
    final container = ProviderContainer(
      overrides: [
        dioProvider.overrideWithValue(dio),
        sesionRepositoryProvider.overrideWith(
          (ref) => SesionRepository(dio),
        ),
      ],
    );
    addTearDown(container.dispose);

    sim.autenticado = true;
    await container.read(sesionNotifierProvider.notifier).refrescarAlArranque();
    expect(container.read(sesionNotifierProvider).autenticado, isTrue);

    sim.autenticado = false;
    await container.read(sesionNotifierProvider.notifier).cargarEstado();
    expect(container.read(sesionNotifierProvider).autenticado, isFalse);
  });
}
