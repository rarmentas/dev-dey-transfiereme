import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'theme/transfiereme_theme.dart';

void main() {
  runApp(const ProviderScope(child: TransfieremeApp()));
}

final GoRouter _router = GoRouter(
  routes: [
    GoRoute(
      path: '/',
      builder: (context, state) => const InicioScaffoldPage(),
    ),
  ],
);

class TransfieremeApp extends StatelessWidget {
  const TransfieremeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Transfiéreme',
      debugShowCheckedModeBanner: false,
      locale: const Locale('es', 'MX'),
      theme: TfTheme.light,
      darkTheme: TfTheme.dark,
      themeMode: ThemeMode.system,
      routerConfig: _router,
    );
  }
}

class InicioScaffoldPage extends StatelessWidget {
  const InicioScaffoldPage({super.key});

  @override
  Widget build(BuildContext context) {
    final esOscuro = Theme.of(context).brightness == Brightness.dark;
    final texto = Theme.of(context).textTheme;

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Image.asset(
                  esOscuro
                      ? 'assets/brand/logo-oscuro.png'
                      : 'assets/brand/logo-claro.png',
                  width: 240,
                  semanticLabel: 'Transfiéreme',
                ),
                const SizedBox(height: 32),
                Text(
                  'Bienvenido a Transfiéreme',
                  style: texto.headlineMedium,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 12),
                Text(
                  'Scaffold local listo. El inicio de sesión del vendedor '
                  'llegará en un siguiente cambio.',
                  style: texto.bodyMedium,
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
