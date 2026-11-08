import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/router/app_router.dart';
import '../../../core/sesion/sesion_notifier.dart';
import '../../../core/ui/ui.dart';
import '../../inicio/data/inicio_resumen.dart';
import '../../inicio/presentation/inicio_providers.dart';
import '../../inicio/presentation/inicio_widgets.dart';

/// Inicio: saludo, «Hoy llevas», acciones de cobro y últimos cobros.
class HomeAutenticadoPage extends ConsumerWidget {
  const HomeAutenticadoPage({super.key});

  Future<void> _refrescar(WidgetRef ref) async {
    try {
      ref.invalidate(inicioResumenProvider);
      await ref.read(inicioResumenProvider.future);
    } catch (_) {
      // El error se muestra en pantalla con «Reintentar».
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sesion = ref.watch(sesionNotifierProvider);
    final estado = sesion.estado;
    final tema = Theme.of(context);

    if (estado == null) {
      // El redirect de GoRouter envía al login si no hay sesión.
      return const SizedBox.shrink();
    }

    final resumen = ref.watch(inicioResumenProvider);
    final comercioTexto = estado.comercio?.nombre ?? 'Sin comercio asignado';
    final inicial = estado.nombreParaSaludo.isNotEmpty
        ? estado.nombreParaSaludo.substring(0, 1).toUpperCase()
        : 'U';

    return Scaffold(
      body: SafeArea(
        child: Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: kMaxAnchoContenido),
            child: RefreshIndicator(
              onRefresh: () => _refrescar(ref),
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(
                  kMargenPantalla,
                  TfSpace.s6,
                  kMargenPantalla,
                  TfSpace.s6,
                ),
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
                              style: tema.textTheme.bodyMedium?.copyWith(
                                color: tema.colorScheme.onSurfaceVariant,
                              ),
                            ),
                            const SizedBox(height: TfSpace.s1),
                            Text(
                              saludoInicio(estado.nombreParaSaludo),
                              style: tema.textTheme.headlineLarge,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
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
                            style: tema.textTheme.headlineSmall?.copyWith(
                              color: tema.colorScheme.onPrimaryContainer,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: TfSpace.s5),
                  resumen.when(
                    skipLoadingOnRefresh: true,
                    skipLoadingOnReload: true,
                    data: (r) => HoyLlevasCard(resumen: r),
                    loading: () => const HoyLlevasCard(cargando: true),
                    error: (error, _) => TfAvisoError(
                      titulo: 'No pudimos cargar tu resumen',
                      mensaje: error.toString(),
                      accion: OutlinedButton(
                        key: const Key('boton_reintentar_inicio'),
                        onPressed: () => ref.invalidate(inicioResumenProvider),
                        child: const Text('Reintentar'),
                      ),
                    ),
                  ),
                  const SizedBox(height: TfSpace.s4),
                  TfCobrarButton(
                    onPressed: () => context.push(kRutaNuevaVenta),
                    icon: const Icon(Icons.qr_code_2_rounded),
                    child: const Text('Cobrar'),
                  ),
                  const SizedBox(height: TfSpace.s3),
                  SizedBox(
                    width: double.infinity,
                    height: 52,
                    child: OutlinedButton.icon(
                      key: const Key('boton_mi_qr'),
                      onPressed: () => context.push(kRutaMiQr),
                      icon: const Icon(Icons.qr_code_rounded),
                      label: const Text('Mi QR'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: tema.colorScheme.primary,
                        side: BorderSide(
                          color: tema.colorScheme.primary,
                          width: 2,
                        ),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(TfRadius.md),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: TfSpace.s6),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          'ÚLTIMOS COBROS',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: tema.textTheme.labelMedium?.copyWith(
                            color: tema.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ),
                      TextButton(
                        onPressed: () => context.go(kRutaMovimientos),
                        style: TextButton.styleFrom(
                          minimumSize: const Size(48, 48),
                        ),
                        child: const Text('Ver todos'),
                      ),
                    ],
                  ),
                  const SizedBox(height: TfSpace.s2),
                  ..._ultimos(resumen, tema),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  List<Widget> _ultimos(AsyncValue<InicioResumen> resumen, ThemeData tema) {
    final r = resumen.asData?.value;
    if (r == null) {
      return const [];
    }
    if (r.recientes.isEmpty) {
      return [
        Card(
          margin: EdgeInsets.zero,
          child: Padding(
            padding: const EdgeInsets.all(TfSpace.s5),
            child: Text(
              'Aún no hay cobros. Toca Cobrar para registrar el primero.',
              textAlign: TextAlign.center,
              style: tema.textTheme.bodyMedium?.copyWith(
                color: tema.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ),
      ];
    }
    return [
      for (var i = 0; i < r.recientes.length; i++) ...[
        if (i > 0) const SizedBox(height: TfSpace.s3),
        CobroRecienteCard(movimiento: r.recientes[i]),
      ],
    ];
  }
}
