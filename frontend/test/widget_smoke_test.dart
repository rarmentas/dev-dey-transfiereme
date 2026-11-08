import 'package:cody/main.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('muestra el título Cody', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: CodyApp()));
    await tester.pumpAndSettle();

    expect(find.text('Cody'), findsWidgets);
    expect(find.textContaining('Bienvenido a Cody'), findsOneWidget);
  });
}
