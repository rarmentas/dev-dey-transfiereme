import 'package:cody/features/asistente_vivo/presentation/asistente_vivo_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('muestra el inicio seguro del asistente', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: MaterialApp(home: AsistenteVivoPage())),
    );
    expect(find.text('Asistente en vivo'), findsWidgets);
    expect(find.byKey(const Key('boton_asistente_vivo')), findsOneWidget);
    expect(find.textContaining('no realiza cambios'), findsOneWidget);
  });
}
