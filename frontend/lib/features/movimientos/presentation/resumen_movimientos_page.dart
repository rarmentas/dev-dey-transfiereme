import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/ui/ui.dart';
import '../data/movimiento.dart';
import '../data/movimientos_repository.dart';
import 'movimientos_providers.dart';

class ResumenMovimientosPage extends ConsumerWidget {
  const ResumenMovimientosPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tema = Theme.of(context);
    final asyncMovimientos = ref.watch(movimientosProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text(
          'Movimientos',
          style: tema.textTheme.headlineLarge,
        ),
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: kMaxAnchoContenido),
          child: RefreshIndicator(
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
                    child: TfVacio(
                      icono: Icons.receipt_long_rounded,
                      titulo: 'Aún no hay movimientos',
                    ),
                  );
                }
                return ListView.separated(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(
                    kMargenPantalla,
                    TfSpace.s3,
                    kMargenPantalla,
                    TfSpace.s6,
                  ),
                  itemCount: movimientos.length,
                  separatorBuilder: (_, _) =>
                      const SizedBox(height: TfSpace.s3),
                  itemBuilder: (context, index) {
                    final movimiento = movimientos[index];
                    final mostrarSeparador = index == 0 ||
                        movimiento.fechaCorta !=
                            movimientos[index - 1].fechaCorta;
                    final tarjeta = _TarjetaMovimiento(
                      movimiento: movimiento,
                      onRenombrar: movimiento.estado == 'pagado'
                          ? () => _renombrar(context, ref, movimiento)
                          : null,
                    );
                    if (mostrarSeparador) {
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Padding(
                            padding: EdgeInsets.only(
                              top: index == 0 ? TfSpace.s1 : TfSpace.s3,
                              bottom: TfSpace.s2,
                            ),
                            child: TfSobretitulo(movimiento.fechaCorta),
                          ),
                          tarjeta,
                        ],
                      );
                    }
                    return tarjeta;
                  },
                );
              },
            ),
          ),
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
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: kMargenPantalla),
                  child: child,
                ),
              ),
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
    return Padding(
      padding: const EdgeInsets.all(TfSpace.s4),
      child: TfAvisoError(
        titulo: mensaje,
        accion: FilledButton(
          onPressed: () async {
            await onReintentar();
          },
          child: const Text('Reintentar'),
        ),
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
    final esVencido = movimiento.estado.toLowerCase().trim() == 'vencido';

    final estiloMonto = (tema.textTheme.titleMedium ?? const TextStyle()).copyWith(
      color: esVencido
          ? tema.colorScheme.onSurfaceVariant
          : tema.colorScheme.onSurface,
      decoration: esVencido ? TextDecoration.lineThrough : null,
      decorationColor: esVencido ? tema.colorScheme.onSurfaceVariant : null,
    );

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(TfSpace.s4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TfIconoCanal(_iconoCanal(movimiento.canal)),
            const SizedBox(width: TfSpace.s3),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      Expanded(
                        child: Text(
                          movimiento.conceptoVisible,
                          overflow: TextOverflow.ellipsis,
                          maxLines: 1,
                          style: (tema.textTheme.titleSmall ?? const TextStyle()).copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      if (onRenombrar != null)
                        IconButton(
                          tooltip: 'Renombrar',
                          onPressed: onRenombrar,
                          visualDensity: VisualDensity.compact,
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(
                            minWidth: 48,
                            minHeight: 48,
                          ),
                          icon: const Icon(Icons.edit_rounded, size: 18),
                        ),
                      const SizedBox(width: TfSpace.s2),
                      Flexible(
                        child: FittedBox(
                          fit: BoxFit.scaleDown,
                          alignment: Alignment.centerRight,
                          child: Text(
                            movimiento.montoFormateado,
                            style: estiloMonto,
                          ),
                        ),
                      ),
                    ],
                  ),
                  if (movimiento.muestraEnviado) ...[
                    const SizedBox(height: TfSpace.s1),
                    Text(
                      'Enviado: ${movimiento.concepto}',
                      style: tema.textTheme.bodySmall?.copyWith(
                        color: tema.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                  const SizedBox(height: TfSpace.s2),
                  Wrap(
                    spacing: TfSpace.s2,
                    runSpacing: TfSpace.s1,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      TfEstadoChip.desde(
                        estado: movimiento.estado,
                        etiqueta: movimiento.etiquetaEstado,
                      ),
                      if (movimiento.esPrueba)
                        Chip(
                          visualDensity: VisualDensity.compact,
                          materialTapTargetSize:
                              MaterialTapTargetSize.shrinkWrap,
                          labelPadding:
                              const EdgeInsets.symmetric(horizontal: TfSpace.s1),
                          padding: EdgeInsets.zero,
                          label: Text(
                            'Prueba',
                            style: tema.textTheme.labelSmall?.copyWith(
                              color: tema.colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ),
                      Text(
                        movimiento.etiquetaCanal,
                        style: tema.textTheme.bodySmall,
                      ),
                      Text(
                        movimiento.fechaCorta,
                        style: tema.textTheme.bodySmall,
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

IconData _iconoCanal(String canal) {
  return switch (canal) {
    'qr_general' => Icons.qr_code_2_rounded,
    'qr_venta' => Icons.storefront_rounded,
    'notificacion' => Icons.phonelink_ring_rounded,
    _ => Icons.payment_rounded,
  };
}
