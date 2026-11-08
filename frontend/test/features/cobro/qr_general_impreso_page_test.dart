import 'package:cody/core/router/app_router.dart';
import 'package:cody/features/cobro/presentation/qr_general_impreso_page.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
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
      find.text('Tu cliente puede pagar con CoDi desde la app de su banco.'),
      findsOneWidget,
    );
    expect(find.textContaining('Esperando'), findsNothing);
    expect(find.textContaining('venció'), findsNothing);
    expect(find.textContaining('vencimiento'), findsNothing);
    expect(_fondosBlancos(), findsOneWidget);
    expect(
      tester.getSize(find.byTooltip('Volver')).height,
      greaterThanOrEqualTo(48),
    );
  });

  testWidgets('cuenta pendiente sin QR cobrable muestra mensaje claro', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 568);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
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
    expect(find.text(kMensajeQrAlActivar), findsOneWidget);
    expect(find.textContaining('Tu cliente puede pagar'), findsNothing);
    expect(find.byType(Card), findsOneWidget);
    expect(_fondosBlancos(), findsNothing);
  });

  testWidgets('cuenta pendiente usa la superficie del tema en claro y oscuro', (
    tester,
  ) async {
    for (final tema in [TfTheme.light, TfTheme.dark]) {
      await tester.pumpWidget(
        MaterialApp(
          key: ValueKey(tema.brightness),
          theme: tema,
          home: const QrGeneralImpresoPage(puedeMostrarQr: false),
        ),
      );
      await tester.pump();

      final texto = tester.widget<Text>(find.text(kMensajeCuentaNoActivaQr));
      expect(texto.style?.color, tema.colorScheme.onSurface);
      expect(texto.style?.fontSize, tema.textTheme.headlineSmall?.fontSize);

      final sigue = tester.widget<Text>(find.text(kMensajeQrAlActivar));
      expect(sigue.style?.color, tema.colorScheme.onSurfaceVariant);

      final icono = tester.widget<Icon>(find.byIcon(Icons.schedule_rounded));
      final tf = tema.extension<TfColors>()!;
      expect(icono.color, tf.pendingText);

      final card = tester.widget<Card>(find.byType(Card));
      expect(
        card.color ?? tema.cardTheme.color,
        tema.colorScheme.surfaceContainerLow,
      );
      expect(_fondosBlancos(), findsNothing);
    }
  });

  testWidgets('sin historial, Volver lleva a inicio', (tester) async {
    final router = GoRouter(
      initialLocation: kRutaMiQr,
      routes: [
        GoRoute(
          path: kRutaMiQr,
          builder: (context, state) =>
              const QrGeneralImpresoPage(puedeMostrarQr: false),
        ),
        GoRoute(
          path: kRutaInicio,
          builder: (context, state) =>
              const Scaffold(body: Text('pantalla inicio')),
        ),
      ],
    );
    addTearDown(router.dispose);
    await tester.pumpWidget(
      MaterialApp.router(theme: TfTheme.dark, routerConfig: router),
    );
    await tester.pump();

    expect(find.byTooltip('Volver'), findsOneWidget);
    await tester.tap(find.byTooltip('Volver'));
    await tester.pumpAndSettle();
    expect(find.text('pantalla inicio'), findsOneWidget);
  });

  testWidgets('con historial, Volver regresa a la pantalla anterior', (
    tester,
  ) async {
    final router = GoRouter(
      initialLocation: '/origen',
      routes: [
        GoRoute(
          path: '/origen',
          builder: (context, state) => const Scaffold(body: Text('origen')),
        ),
        GoRoute(
          path: kRutaMiQr,
          builder: (context, state) => const QrGeneralImpresoPage(
            puedeMostrarQr: true,
            qrString: qrStringMock,
          ),
        ),
      ],
    );
    addTearDown(router.dispose);
    await tester.pumpWidget(
      MaterialApp.router(theme: TfTheme.light, routerConfig: router),
    );
    router.push(kRutaMiQr);
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Volver'));
    await tester.pumpAndSettle();
    expect(find.text('origen'), findsOneWidget);
    expect(find.byType(QrImageView), findsNothing);
  });

  testWidgets('en web ancha el bloqueo cabe en la columna de 480', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1200, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        theme: TfTheme.light,
        home: const QrGeneralImpresoPage(puedeMostrarQr: false),
      ),
    );
    await tester.pump();

    expect(tester.getSize(find.byType(Card)).width, lessThanOrEqualTo(480));
    expect(find.byTooltip('Volver'), findsOneWidget);
  });
}

Finder _fondosBlancos() {
  return find.byWidgetPredicate((widget) {
    if (widget is Container && widget.decoration is BoxDecoration) {
      return (widget.decoration! as BoxDecoration).color == Colors.white;
    }
    return false;
  });
}
