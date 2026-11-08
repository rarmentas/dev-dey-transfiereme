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
        home: const QrGeneralImpresoPage(
          puedeMostrarQr: true,
          qrString: qrStringMock,
        ),
      ),
    );
    await tester.pump();

    expect(find.byType(QrImageView), findsOneWidget);
    expect(find.text('Mi QR'), findsOneWidget);
    expect(
      find.text(
        'Tu cliente puede pagar con CoDi desde la app de su banco.',
      ),
      findsOneWidget,
    );
    expect(find.textContaining('Esperando'), findsNothing);
    expect(find.textContaining('venció'), findsNothing);
    expect(find.textContaining('vencimiento'), findsNothing);
  });

  testWidgets('cuenta pendiente sin QR cobrable muestra mensaje claro',
      (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: TfTheme.light,
        home: const QrGeneralImpresoPage(puedeMostrarQr: false),
      ),
    );
    await tester.pump();

    expect(find.byType(QrImageView), findsNothing);
    expect(find.text('Mi QR'), findsOneWidget);
    expect(find.text(kMensajeCuentaNoActivaQr), findsOneWidget);
    expect(
      find.textContaining('Tu cliente puede pagar'),
      findsNothing,
    );
  });

  testWidgets(
    'cuenta pendiente en tema oscuro usa tinta oscura sobre tarjeta blanca',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: TfTheme.dark,
          home: const QrGeneralImpresoPage(puedeMostrarQr: false),
        ),
      );
      await tester.pump();

      expect(find.text(kMensajeCuentaNoActivaQr), findsOneWidget);

      final texto = tester.widget<Text>(find.text(kMensajeCuentaNoActivaQr));
      expect(texto.style?.color, TfColors.light.pendingText);
    },
  );
}
