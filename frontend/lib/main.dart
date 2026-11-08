import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/router/app_router.dart';
import 'theme/transfiereme_theme.dart';

void main() {
  runApp(const ProviderScope(child: TransfieremeApp()));
}

class TransfieremeApp extends ConsumerWidget {
  const TransfieremeApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);

    return MaterialApp.router(
      title: 'Transfiéreme',
      debugShowCheckedModeBanner: false,
      locale: const Locale('es', 'MX'),
      theme: TfTheme.light,
      darkTheme: TfTheme.dark,
      themeMode: ThemeMode.system,
      routerConfig: router,
    );
  }
}
