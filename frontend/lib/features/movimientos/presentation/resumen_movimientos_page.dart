import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/transfiereme_theme.dart';
import '../data/movimiento.dart';
import '../data/movimientos_repository.dart';
import 'movimientos_providers.dart';

class ResumenMovimientosPage extends ConsumerWidget {
  const ResumenMovimientosPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncMovimientos = ref.watch(movimientosProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Movimientos')),
      body: RefreshIndicator(
        onRefresh: () => _recargar(ref),
        child: asyncMovimientos.when(
          loading: () =>
              const _EstadoCentrado(child: CircularProgressIndicator()),
          error: (error, _) => _EstadoCentrado(
            child: _ErrorMovimientos(
              mensaje: mensajeErrorMovimientos(error),
              onReintentar: () => _recargar(ref),
            ),
          ),
          data: (movimientos) {
            if (movimientos.isEmpty) {
              return const _EstadoCentrado(
                child: Text('Aún no hay movimientos'),
              );
            }
            return ListView.separated(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
              itemCount: movimientos.length,
              separatorBuilder: (_, _) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                return _TarjetaMovimiento(movimiento: movimientos[index]);
              },
            );
          },
        ),
      ),
    );
  }
}

String mensajeErrorMovimientos(Object error) {
  if (error is MovimientosApiException) {
    return error.mensaje;
  }
  return 'No pudimos cargar los movimientos. Intente de nuevo.';
}

Future<void> _recargar(WidgetRef ref) async {
  final recarga = ref.refresh(movimientosProvider.future);
  try {
    await recarga;
  } catch (_) {
    // El provider conserva el error y la pantalla lo muestra.
  }
}

class _EstadoCentrado extends StatelessWidget {
  const _EstadoCentrado({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        return ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            ConstrainedBox(
              constraints: BoxConstraints(minHeight: constraints.maxHeight),
              child: Center(child: child),
            ),
          ],
        );
      },
    );
  }
}

class _ErrorMovimientos extends StatelessWidget {
  const _ErrorMovimientos({required this.mensaje, required this.onReintentar});

  final String mensaje;
  final Future<void> Function() onReintentar;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            mensaje,
            style: tema.textTheme.bodyLarge?.copyWith(
              color: tema.colorScheme.error,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: () async {
              await onReintentar();
            },
            child: const Text('Reintentar'),
          ),
        ],
      ),
    );
  }
}

class _TarjetaMovimiento extends StatelessWidget {
  const _TarjetaMovimiento({required this.movimiento});

  final Movimiento movimiento;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final tf = tema.extension<TfColors>();
    final colores = _coloresEstado(movimiento.estado, tf, tema.colorScheme);

    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(
                    movimiento.conceptoVisible,
                    style: tema.textTheme.titleMedium,
                  ),
                ),
                const SizedBox(width: 12),
                Text(
                  movimiento.montoFormateado,
                  style: tema.textTheme.titleMedium,
                ),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Text(movimiento.etiquetaCanal, style: tema.textTheme.bodySmall),
                DecoratedBox(
                  decoration: BoxDecoration(
                    color: colores.fondo,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 2,
                    ),
                    child: Text(
                      movimiento.etiquetaEstado,
                      style: tema.textTheme.labelMedium?.copyWith(
                        color: colores.texto,
                      ),
                    ),
                  ),
                ),
                if (movimiento.esPrueba)
                  Chip(
                    visualDensity: VisualDensity.compact,
                    materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    labelPadding: const EdgeInsets.symmetric(horizontal: 6),
                    padding: EdgeInsets.zero,
                    label: Text('Prueba', style: tema.textTheme.labelSmall),
                  ),
              ],
            ),
            const SizedBox(height: 4),
            Text(movimiento.fechaCorta, style: tema.textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

class _ColoresEstado {
  const _ColoresEstado(this.texto, this.fondo);

  final Color texto;
  final Color fondo;
}

_ColoresEstado _coloresEstado(String estado, TfColors? tf, ColorScheme scheme) {
  switch (estado) {
    case 'pagado':
      return _ColoresEstado(
        tf?.paidText ?? scheme.tertiary,
        tf?.paidContainer ?? scheme.tertiaryContainer,
      );
    case 'pendiente':
      return _ColoresEstado(
        tf?.pendingText ?? scheme.onSecondaryContainer,
        tf?.pendingContainer ?? scheme.secondaryContainer,
      );
    case 'vencido':
      return _ColoresEstado(
        tf?.expiredText ?? scheme.error,
        tf?.expiredContainer ?? scheme.errorContainer,
      );
    default:
      return _ColoresEstado(
        scheme.onSurfaceVariant,
        scheme.surfaceContainerHigh,
      );
  }
}
