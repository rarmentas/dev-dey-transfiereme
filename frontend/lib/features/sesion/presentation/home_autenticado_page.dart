import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/router/app_router.dart';
import '../../../core/sesion/sesion_notifier.dart';
import '../../../core/ui/ui.dart';

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
    final inicial = estado.nombreParaSaludo.isNotEmpty
        ? estado.nombreParaSaludo.substring(0, 1).toUpperCase()
        : 'U';

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: kMaxAnchoContenido),
            child: LayoutBuilder(
              builder: (context, constraints) {
                final minH = constraints.maxHeight.isFinite
                    ? (constraints.maxHeight - (TfSpace.s6 * 2))
                        .clamp(0.0, double.infinity)
                    : 0.0;

                return SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(
                    horizontal: kMargenPantalla,
                    vertical: TfSpace.s6,
                  ),
                  child: ConstrainedBox(
                    constraints: BoxConstraints(minHeight: minH),
                    child: IntrinsicHeight(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.center,
                            children: [
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      comercioTexto,
                                      style:
                                          tema.textTheme.bodyMedium?.copyWith(
                                        color: tema.colorScheme.onSurfaceVariant,
                                      ),
                                    ),
                                    const SizedBox(height: TfSpace.s1),
                                    Text(
                                      'Hola, ${estado.nombreParaSaludo}',
                                      style: tema.textTheme.headlineLarge,
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(width: TfSpace.s4),
                              ExcludeSemantics(
                                child: Container(
                                  width: 48,
                                  height: 48,
                                  decoration: BoxDecoration(
                                    color: tema.colorScheme.primaryContainer,
                                    shape: BoxShape.circle,
                                  ),
                                  alignment: Alignment.center,
                                  child: Text(
                                    inicial,
                                    style:
                                        tema.textTheme.headlineSmall?.copyWith(
                                      color:
                                          tema.colorScheme.onPrimaryContainer,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: TfSpace.s8),
                          const Spacer(),
                          TfCobrarButton(
                            onPressed: () => context.push(kRutaNuevaVenta),
                            icon: const Icon(Icons.qr_code_2_rounded),
                            child: const Text('Nueva venta'),
                          ),
                          const SizedBox(height: TfSpace.s3),
                          SizedBox(
                            width: double.infinity,
                            height: 52,
                            child: OutlinedButton.icon(
                              onPressed: () => context.push(kRutaMovimientos),
                              icon: const Icon(Icons.receipt_long_rounded),
                              label: const Text('Ver movimientos'),
                              style: OutlinedButton.styleFrom(
                                side: BorderSide(
                                  color: tema.colorScheme.primary,
                                  width: 2,
                                ),
                                shape: RoundedRectangleBorder(
                                  borderRadius:
                                      BorderRadius.circular(TfRadius.md),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: TfSpace.s3),
                          SizedBox(
                            width: double.infinity,
                            height: 52,
                            child: OutlinedButton.icon(
                              onPressed: () => context.push(kRutaTablero),
                              icon: const Icon(Icons.bar_chart_rounded),
                              label: const Text('Ver tablero'),
                              style: OutlinedButton.styleFrom(
                                side: BorderSide(
                                  color: tema.colorScheme.primary,
                                  width: 2,
                                ),
                                shape: RoundedRectangleBorder(
                                  borderRadius:
                                      BorderRadius.circular(TfRadius.md),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: TfSpace.s3),
                          SizedBox(
                            width: double.infinity,
                            height: 52,
                            child: OutlinedButton.icon(
                              key: const Key('boton_registrar_clabe'),
                              onPressed: () => context.push(kRutaRegistrarClabe),
                              icon: const Icon(Icons.account_balance_rounded),
                              label: const Text('Registrar CLABE'),
                              style: OutlinedButton.styleFrom(
                                side: BorderSide(
                                  color: tema.colorScheme.outlineVariant,
                                  width: 1.5,
                                ),
                                foregroundColor: tema.colorScheme.onSurface,
                                shape: RoundedRectangleBorder(
                                  borderRadius:
                                      BorderRadius.circular(TfRadius.md),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: TfSpace.s4),
                          Center(
                            child: TextButton.icon(
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
                              icon: sesion.cargando
                                  ? const SizedBox.shrink()
                                  : const Icon(Icons.logout_rounded, size: 20),
                              label: sesion.cargando
                                  ? const SizedBox(
                                      height: 20,
                                      width: 20,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                      ),
                                    )
                                  : const Text('Salir'),
                              style: TextButton.styleFrom(
                                foregroundColor:
                                    tema.colorScheme.onSurfaceVariant,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ),
      ),
    );
  }
}
