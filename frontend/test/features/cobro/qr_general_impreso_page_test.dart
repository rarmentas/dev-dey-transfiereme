import 'package:cody/features/cobro/presentation/qr_general_impreso_page.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qr_flutter/qr_flutter.dart';

void main() {
  const qrStringMock = 'cody-dev://qr/plan-mock';

  testWidgets('renderiza el QR desde qrString mock', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: TfTheme.light,
        home: const QrGeneralImpresoPage(qrString: qrStringMock),
      ),
    );
    await tester.pump();

    expect(find.byType(QrImageView), findsOneWidget);
    expect(find.text('Mi QR'), findsOneWidget);
    expect(find.textContaining('Esperando'), findsNothing);
    expect(find.textContaining('venció'), findsNothing);
    expect(find.textContaining('vencimiento'), findsNothing);
  });
}
