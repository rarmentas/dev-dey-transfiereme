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
    expect(find.text('Tortillería La Esperanza'), findsOneWidget);
    expect(find.text('Salir'), findsOneWidget);

    await tester.tap(find.byKey(const Key('opcion_mi_qr')));
    await tester.pumpAndSettle();
    expect(find.text('destino qr'), findsOneWidget);
  });
}
