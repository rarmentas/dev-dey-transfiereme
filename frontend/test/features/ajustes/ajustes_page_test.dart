import 'package:cody/core/router/app_router.dart';
import 'package:cody/core/sesion/sesion_models.dart';
import 'package:cody/core/sesion/sesion_notifier.dart';
import 'package:cody/core/sesion/sesion_view_state.dart';
import 'package:cody/features/ajustes/presentation/ajustes_page.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

class _SesionSinNombre extends SesionNotifier {
  @override
  SesionViewState build() => const SesionViewState(
    resuelto: true,
    cargando: false,
    estado: EstadoSesion(
      usuario: 'demo',
      correo: 'demo@cody.mx',
      nombre: '',
      apellidos: '',
      comercio: ComercioResumen(id: 1, nombre: 'Abarrotes Demo'),
    ),
  );
}

class _SesionFija extends SesionNotifier {
  @override
  SesionViewState build() => const SesionViewState(
    resuelto: true,
    cargando: false,
    estado: EstadoSesion(
      usuario: 'lupe',
      correo: 'lupe@tortilleria.mx',
      nombre: 'Lupe',
      apellidos: 'García',
      comercio: ComercioResumen(id: 1, nombre: 'Tortillería La Esperanza'),
    ),
  );
}

void main() {
  testWidgets('muestra datos de la cuenta y navega a Mi QR', (tester) async {
    final router = GoRouter(
      initialLocation: kRutaAjustes,
      routes: [
        GoRoute(
          path: kRutaAjustes,
          builder: (context, state) => const AjustesPage(),
        ),
        GoRoute(
          path: kRutaMiQr,
          builder: (context, state) => const Scaffold(body: Text('destino qr')),
        ),
      ],
    );
    addTearDown(router.dispose);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [sesionNotifierProvider.overrideWith(_SesionFija.new)],
        child: MaterialApp.router(theme: TfTheme.light, routerConfig: router),
      ),
    );
    await tester.pump();

    expect(find.text('Ajustes'), findsOneWidget);
    expect(find.text('Lupe García'), findsOneWidget);
    expect(find.text('lupe@tortilleria.mx'), findsOneWidget);
    final correo = tester.widget<Text>(find.text('lupe@tortilleria.mx'));
    expect(correo.style?.color, TfTheme.light.colorScheme.onSurfaceVariant);
    expect(find.text('Tortillería La Esperanza'), findsOneWidget);
    expect(find.text('Salir'), findsOneWidget);
    final salir = tester.widget<OutlinedButton>(
      find.byKey(const Key('boton_salir')),
    );
    expect(
      salir.style?.foregroundColor?.resolve(<WidgetState>{}),
      TfTheme.light.colorScheme.onSurfaceVariant,
    );
    expect(
      salir.style?.side?.resolve(<WidgetState>{})?.color,
      TfTheme.light.colorScheme.outlineVariant,
    );
    expect(
      tester.getSize(find.byKey(const Key('boton_salir'))).height,
      greaterThanOrEqualTo(48),
    );
    expect(
      tester.getSize(find.byType(Card).first).width,
      lessThanOrEqualTo(480),
    );

    await tester.tap(find.byKey(const Key('opcion_mi_qr')));
    await tester.pumpAndSettle();
    expect(find.text('destino qr'), findsOneWidget);
  });

  testWidgets('sin nombre el correo es un dato y no el título', (tester) async {
    final router = GoRouter(
      initialLocation: kRutaAjustes,
      routes: [
        GoRoute(
          path: kRutaAjustes,
          builder: (context, state) => const AjustesPage(),
        ),
      ],
    );
    addTearDown(router.dispose);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [sesionNotifierProvider.overrideWith(_SesionSinNombre.new)],
        child: MaterialApp.router(theme: TfTheme.light, routerConfig: router),
      ),
    );
    await tester.pump();

    final correo = tester.widget<Text>(find.text('demo@cody.mx'));
    expect(correo.style?.color, TfTheme.light.colorScheme.onSurfaceVariant);
    expect(
      correo.style?.fontSize,
      TfTheme.light.textTheme.bodyMedium?.fontSize,
    );
    expect(correo.style?.fontWeight, FontWeight.w400);
    expect(find.text('Abarrotes Demo'), findsOneWidget);
  });
}
