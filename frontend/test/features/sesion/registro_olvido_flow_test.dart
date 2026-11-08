import 'package:cody/core/network/providers.dart';
import 'package:flutter/material.dart';
import 'package:cody/core/sesion/registro_olvido_repository.dart';
import 'package:cody/core/sesion/sesion_providers.dart';
import 'package:cody/core/sesion/sesion_repository.dart';
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
        handler.next(options);
      },
    ),
  );
}

void main() {
  testWidgets('enlace Cree su cuenta abre registro', (tester) async {
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

    expect(find.text('Cree su cuenta'), findsWidgets);
    expect(find.text('Enviar código'), findsOneWidget);
  });

  testWidgets('flujo registro mock vuelve al login con aviso', (tester) async {
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

    await tester.enterText(
      find.byType(TextFormField).at(0),
      'nuevo@ejemplo.mx',
    );
    await tester.enterText(
      find.byType(TextFormField).at(1),
      'Clave-segura-9',
    );
    await tester.tap(find.text('Enviar código'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextFormField).first, '123456');
    await tester.tap(find.text('Confirmar cuenta'));
    await tester.pumpAndSettle();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('Entra a cobrar'), findsOneWidget);
    expect(
      find.text('Su cuenta quedó lista. Ya puede entrar.'),
      findsOneWidget,
    );
  });
}
