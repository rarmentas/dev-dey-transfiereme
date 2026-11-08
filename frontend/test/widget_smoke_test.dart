import 'package:cody/main.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('muestra la marca Transfiéreme', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: TransfieremeApp()));
    await tester.pumpAndSettle();

    expect(find.bySemanticsLabel('Transfiéreme'), findsOneWidget);
    expect(find.text('Bienvenido a Transfiéreme'), findsOneWidget);
  });

  testWidgets('usa el tema Transfiéreme con la extensión de estados', (
    tester,
  ) async {
    await tester.pumpWidget(const ProviderScope(child: TransfieremeApp()));
    await tester.pumpAndSettle();

    final context = tester.element(find.byType(InicioScaffoldPage));
    final theme = Theme.of(context);
    expect(theme.colorScheme.primary, tfLightScheme.primary);
    expect(theme.extension<TfColors>(), isNotNull);
  });
}
