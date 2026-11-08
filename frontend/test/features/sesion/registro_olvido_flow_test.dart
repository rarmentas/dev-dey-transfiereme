import 'package:cody/core/network/providers.dart';
import 'package:flutter/material.dart';
import 'package:cody/core/sesion/registro_olvido_repository.dart';
import 'package:cody/core/sesion/sesion_providers.dart';
import 'package:cody/core/sesion/sesion_repository.dart';
import 'package:cody/features/sesion/presentation/widgets/reenvio_codigo_button.dart';
import 'package:cody/main.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import '../../support/mock_sesion_api.dart';

void _mockRegistroOlvido(Dio dio) {
  dio.interceptors.insert(
    0,
    InterceptorsWrapper(
      onRequest: (options, handler) {
        final path = options.path;
        if (path.contains('/api/sesion/alta/solicitar')) {
          handler.resolve(
            Response(
              requestOptions: options,
              statusCode: 200,
              data: {
                'detail':
                    'Enviamos un código a su correo. Revise su bandeja de entrada.',
              },
            ),
          );
          return;
        }
        if (path.contains('/api/sesion/alta/confirmar')) {
          handler.resolve(
            Response(
              requestOptions: options,
              statusCode: 200,
              data: {'detail': 'Su cuenta quedó lista. Ya puede entrar.'},
            ),
          );
          return;
        }
        if (path.contains('/api/sesion/olvido/solicitar')) {
          handler.resolve(
            Response(
              requestOptions: options,
              statusCode: 200,
              data: {
                'detail':
                    'Si existe una cuenta con ese correo, recibirá un código en breve.',
              },
            ),
          );
          return;
        }
        if (path.contains('/api/sesion/olvido/restablecer')) {
          handler.resolve(
            Response(
              requestOptions: options,
              statusCode: 200,
              data: {
                'detail': 'Su contraseña quedó actualizada. Ya puede entrar.',
              },
            ),
          );
          return;
        }
        handler.next(options);
      },
    ),
  );
}

void main() {
  testWidgets('enlace Cree su cuenta abre modal de registro', (tester) async {
    final dio = crearDioPrueba();
    prepararDioConSesion(dio);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          dioProvider.overrideWithValue(dio),
          sesionRepositoryProvider.overrideWith(
            (ref) => SesionRepository(dio),
          ),
          registroOlvidoRepositoryProvider.overrideWith(
            (ref) => RegistroOlvidoRepository(dio),
          ),
        ],
        child: const TransfieremeApp(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    await tester.tap(find.text('Cree su cuenta'));
    await tester.pumpAndSettle();

    expect(find.text('Confirme su contraseña'), findsOneWidget);
    expect(find.text('Continuar'), findsOneWidget);
    expect(find.text('Entra a cobrar'), findsOneWidget);
  });

  testWidgets('registro rechaza contraseñas que no coinciden', (tester) async {
    final dio = crearDioPrueba();
    prepararDioConSesion(dio);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          dioProvider.overrideWithValue(dio),
          sesionRepositoryProvider.overrideWith(
            (ref) => SesionRepository(dio),
          ),
          registroOlvidoRepositoryProvider.overrideWith(
            (ref) => RegistroOlvidoRepository(dio),
          ),
        ],
        child: const TransfieremeApp(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    await tester.tap(find.text('Cree su cuenta'));
    await tester.pumpAndSettle();

    final campos = find.descendant(
      of: find.byType(Dialog),
      matching: find.byType(TextFormField),
    );
    await tester.enterText(campos.at(0), 'nuevo@ejemplo.mx');
    await tester.enterText(campos.at(1), 'Clave-segura-9');
    await tester.enterText(campos.at(2), 'Otra-clave-9');
    await tester.tap(find.text('Continuar'));
    await tester.pumpAndSettle();

    expect(find.text('Las contraseñas no coinciden.'), findsOneWidget);
  });

  testWidgets('flujo registro mock entra e inicia en home', (tester) async {
    final dio = crearDioPrueba();
    prepararDioConSesion(dio);
    _mockRegistroOlvido(dio);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          dioProvider.overrideWithValue(dio),
          sesionRepositoryProvider.overrideWith(
            (ref) => SesionRepository(dio),
          ),
          registroOlvidoRepositoryProvider.overrideWith(
            (ref) => RegistroOlvidoRepository(dio),
          ),
        ],
        child: const TransfieremeApp(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    await tester.tap(find.text('Cree su cuenta'));
    await tester.pumpAndSettle();

    final paso1 = find.descendant(
      of: find.byType(Dialog),
      matching: find.byType(TextFormField),
    );
    await tester.enterText(paso1.at(0), 'nuevo@ejemplo.mx');
    await tester.enterText(paso1.at(1), 'Clave-segura-9');
    await tester.enterText(paso1.at(2), 'Clave-segura-9');
    await tester.tap(find.text('Continuar'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pumpAndSettle();
    await tester.pump();

    final botonReenvio = find.descendant(
      of: find.byType(Dialog),
      matching: find.byKey(const Key('boton_reenviar_codigo')),
    );
    expect(
      tester.widget<TextButton>(botonReenvio).onPressed,
      isNull,
    );
    expect(find.textContaining('Enviar otro código ('), findsOneWidget);

    final codigo = find.descendant(
      of: find.byType(Dialog),
      matching: find.byType(TextFormField),
    );
    await tester.enterText(codigo.first, '123456');
    await tester.tap(find.text('Confirmar cuenta'));
    await tester.pumpAndSettle();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.text('Hola, Lupe'), findsOneWidget);
    expect(find.text('Entra a cobrar'), findsNothing);
  });

  testWidgets('olvido mock cierra modal y muestra snackbar', (tester) async {
    final dio = crearDioPrueba();
    prepararDioConSesion(dio);
    _mockRegistroOlvido(dio);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          dioProvider.overrideWithValue(dio),
          sesionRepositoryProvider.overrideWith(
            (ref) => SesionRepository(dio),
          ),
          registroOlvidoRepositoryProvider.overrideWith(
            (ref) => RegistroOlvidoRepository(dio),
          ),
        ],
        child: const TransfieremeApp(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    await tester.tap(find.text('¿Olvidó su contraseña?'));
    await tester.pumpAndSettle();

    final correoOlvido = find.descendant(
      of: find.byType(Dialog),
      matching: find.byType(TextFormField),
    );
    await tester.enterText(correoOlvido.first, 'vendedor@demo.mx');
    await tester.tap(find.text('Enviar código'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pumpAndSettle();

    final paso2 = find.descendant(
      of: find.byType(Dialog),
      matching: find.byType(TextFormField),
    );
    await tester.enterText(paso2.at(0), '123456');
    await tester.enterText(paso2.at(1), 'Nueva-clave-9');
    await tester.enterText(paso2.at(2), 'Nueva-clave-9');
    await tester.tap(find.text('Actualizar contraseña'));
    await tester.pumpAndSettle();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('Entra a cobrar'), findsOneWidget);
    expect(
      find.text('Su contraseña quedó actualizada. Ya puede entrar.'),
      findsOneWidget,
    );
  });

  testWidgets('reenvío deshabilita el botón tras enviar', (tester) async {
    var llamadas = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ReenvioCodigoButton(
            cooldown: const Duration(seconds: 2),
            onReenviar: () async {
              llamadas++;
              return true;
            },
          ),
        ),
      ),
    );

    await tester.tap(find.byKey(const Key('boton_reenviar_codigo')));
    await tester.pump();
    await tester.pump();

    expect(llamadas, 1);
    final boton = tester.widget<TextButton>(
      find.byKey(const Key('boton_reenviar_codigo')),
    );
    expect(boton.onPressed, isNull);
    expect(find.textContaining('Enviar otro código ('), findsOneWidget);
  });

  testWidgets('reenvío fallido no inicia espera', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ReenvioCodigoButton(
            onReenviar: () async => false,
          ),
        ),
      ),
    );

    await tester.tap(find.byKey(const Key('boton_reenviar_codigo')));
    await tester.pump();

    final boton = tester.widget<TextButton>(
      find.byKey(const Key('boton_reenviar_codigo')),
    );
    expect(boton.onPressed, isNotNull);
    expect(find.text('Enviar otro código'), findsOneWidget);
  });
}
