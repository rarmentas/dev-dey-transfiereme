import 'package:cody/core/network/providers.dart';
import 'package:cody/core/sesion/sesion_providers.dart';
import 'package:cody/core/sesion/sesion_repository.dart';
import 'package:cody/features/sesion/presentation/login_page.dart';
import 'package:cody/main.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/mock_sesion_api.dart';

void main() {
  testWidgets('muestra la marca Transfiéreme', (tester) async {
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

    expect(find.bySemanticsLabel('Transfiéreme'), findsOneWidget);
    expect(find.text('Entra a cobrar'), findsOneWidget);
  });

  testWidgets('usa el tema Transfiéreme con la extensión de estados', (
    tester,
  ) async {
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

    final context = tester.element(find.byType(LoginPage));
    final theme = Theme.of(context);
    expect(theme.colorScheme.primary, tfLightScheme.primary);
    expect(theme.extension<TfColors>(), isNotNull);
  });
}
