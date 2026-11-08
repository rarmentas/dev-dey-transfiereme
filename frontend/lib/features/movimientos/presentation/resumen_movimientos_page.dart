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
                final movimiento = movimientos[index];
                return _TarjetaMovimiento(
                  movimiento: movimiento,
                  onRenombrar: movimiento.estado == 'pagado'
                      ? () => _renombrar(context, ref, movimiento)
                      : null,
                );
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

Future<void> _renombrar(
  BuildContext context,
  WidgetRef ref,
  Movimiento movimiento,
) async {
  final nuevo = await showDialog<String>(
    context: context,
    builder: (context) =>
        _DialogoRenombrar(inicial: movimiento.conceptoVisible),
  );
  if (nuevo == null || !context.mounted) {
    return;
  }
  final messenger = ScaffoldMessenger.of(context);
  try {
    await ref
        .read(movimientosRepositoryProvider)
        .renombrarConcepto(movimiento.id, nuevo);
    ref.invalidate(movimientosProvider);
  } catch (error) {
    messenger.showSnackBar(
      SnackBar(content: Text(mensajeErrorMovimientos(error))),
    );
  }
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

class _DialogoRenombrar extends StatefulWidget {
  const _DialogoRenombrar({required this.inicial});

  final String inicial;

  @override
  State<_DialogoRenombrar> createState() => _DialogoRenombrarState();
}

class _DialogoRenombrarState extends State<_DialogoRenombrar> {
  late final TextEditingController _control = TextEditingController(
    text: widget.inicial,
  );

  @override
  void dispose() {
    _control.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Renombrar'),
      content: TextField(
        controller: _control,
        autofocus: true,
        decoration: const InputDecoration(labelText: 'Concepto visible'),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancelar'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, _control.text),
          child: const Text('Guardar'),
        ),
      ],
    );
  }
}

class _TarjetaMovimiento extends StatelessWidget {
  const _TarjetaMovimiento({required this.movimiento, this.onRenombrar});

  final Movimiento movimiento;
  final VoidCallback? onRenombrar;

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
                if (onRenombrar != null)
                  IconButton(
                    tooltip: 'Renombrar',
                    onPressed: onRenombrar,
                    visualDensity: VisualDensity.compact,
                    icon: const Icon(Icons.edit_outlined),
                  ),
                const SizedBox(width: 12),
                Text(
                  movimiento.montoFormateado,
                  style: tema.textTheme.titleMedium,
                ),
              ],
            ),
            if (movimiento.muestraEnviado) ...[
              const SizedBox(height: 4),
              Text(
                'Enviado: ${movimiento.concepto}',
                style: tema.textTheme.bodySmall?.copyWith(
                  color: tema.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
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
