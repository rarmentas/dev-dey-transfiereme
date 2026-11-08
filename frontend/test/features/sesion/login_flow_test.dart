import 'package:cody/core/network/providers.dart';
import 'package:cody/core/sesion/sesion_notifier.dart';
import 'package:cody/core/sesion/sesion_providers.dart';
import 'package:cody/core/sesion/sesion_repository.dart';
import 'package:cody/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/mock_inicio_api.dart';
import '../../support/mock_sesion_api.dart';

Future<void> _llenarLogin(WidgetTester tester, String correo, String clave) async {
  await tester.enterText(find.byKey(const Key('campo_correo')), correo);
  await tester.enterText(find.byKey(const Key('campo_contrasena')), clave);
}

void main() {
  testWidgets('credenciales válidas navegan al home autenticado', (
    tester,
  ) async {
    final dio = crearDioPrueba();
    prepararDioConSesion(dio);
    instalarInicioApi(dio);

    final container = ProviderContainer(
      overrides: [
        dioProvider.overrideWithValue(dio),
        sesionRepositoryProvider.overrideWith(
          (ref) => SesionRepository(dio),
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

    expect(find.text('Entra a cobrar'), findsOneWidget);

    await _llenarLogin(tester, 'lupe@tortilleria.mx', 'clave-segura');
    await tester.tap(find.byKey(const Key('boton_entrar')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    // Deja terminar la carga del resumen de inicio.
    await tester.pump(const Duration(milliseconds: 400));

    expect(container.read(sesionNotifierProvider).autenticado, isTrue);
    expect(find.text('Hola, Lupe'), findsOneWidget);
    expect(find.text('Tortillería La Esperanza'), findsOneWidget);
  });

  testWidgets('credenciales inválidas muestran el detalle del API', (
    tester,
  ) async {
    final dio = crearDioPrueba();
    final sim = prepararDioConSesion(dio);
    sim.rechazarEntrada = true;

    final container = ProviderContainer(
      overrides: [
        dioProvider.overrideWithValue(dio),
        sesionRepositoryProvider.overrideWith(
          (ref) => SesionRepository(dio),
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
    await tester.pump(const Duration(milliseconds: 300));

    await _llenarLogin(tester, 'mal@ejemplo.mx', 'incorrecta');
    await tester.tap(find.byKey(const Key('boton_entrar')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.text('Revise el correo y la contraseña.'), findsOneWidget);
    expect(find.text('Hola, Lupe'), findsNothing);
  });
}
