import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/router/app_router.dart';
import '../../../core/sesion/sesion_notifier.dart';

class HomeAutenticadoPage extends ConsumerWidget {
  const HomeAutenticadoPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sesion = ref.watch(sesionNotifierProvider);
    final estado = sesion.estado;
    final tema = Theme.of(context);

    if (estado == null) {
      // El redirect de GoRouter envía al login si no hay sesión.
      return const SizedBox.shrink();
    }

    final comercioTexto = estado.comercio?.nombre ?? 'Sin comercio asignado';

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Hola, ${estado.nombreParaSaludo}',
                style: tema.textTheme.headlineMedium,
              ),
              const SizedBox(height: 8),
              Text(
                comercioTexto,
                style: tema.textTheme.bodyLarge,
              ),
              const Spacer(),
              FilledButton(
                onPressed: () => context.push(kRutaNuevaVenta),
                child: const Text('Nueva venta'),
              ),
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: () => context.push(kRutaMovimientos),
                child: const Text('Ver movimientos'),
              ),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: sesion.cargando
                    ? null
                    : () async {
                        await ref
                            .read(sesionNotifierProvider.notifier)
                            .salir();
                        if (context.mounted) {
                          context.go(kRutaEntrar);
                        }
                      },
                child: sesion.cargando
                    ? const SizedBox(
                        height: 22,
                        width: 22,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Salir'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
