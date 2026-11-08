import 'package:flutter/material.dart';

import '../../../core/fecha/dia_cdmx.dart';
import '../../../core/ui/ui.dart';
import '../../../theme/transfiereme_theme.dart';
import '../../movimientos/data/movimiento.dart';
import '../data/inicio_resumen.dart';

/// Tarjeta «Hoy llevas» con el total confirmado de hoy.
class HoyLlevasCard extends StatelessWidget {
  const HoyLlevasCard({super.key, this.resumen, this.cargando = false});

  final InicioResumen? resumen;
  final bool cargando;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final tf = tema.extension<TfColors>()!;
    final suave = tema.colorScheme.onSurfaceVariant;
    final r = resumen;

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(TfSpace.s5),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Hoy llevas',
              style: tema.textTheme.titleSmall?.copyWith(color: suave),
            ),
            const SizedBox(height: TfSpace.s2),
            if (cargando || r == null)
              const SizedBox(
                height: 48,
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ),
              )
            else ...[
              FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: Text(
                  r.totalHoy,
                  key: const Key('total_hoy'),
                  style: tema.textTheme.displaySmall,
                ),
              ),
              const SizedBox(height: TfSpace.s1),
              Text.rich(
                TextSpan(
                  children: [
                    TextSpan(
                      text: r.cobrosHoy == 1 ? '1 cobro' : '${r.cobrosHoy} cobros',
                      style: TextStyle(
                        color: tf.paidText,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    TextSpan(
                      text: ' · ${r.pendientesHoy} '
                          '${r.pendientesHoy == 1 ? 'pendiente' : 'pendientes'}',
                      style: TextStyle(color: suave),
                    ),
                  ],
                ),
                style: tema.textTheme.bodyMedium,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Movimiento compacto para «Últimos cobros».
class CobroRecienteCard extends StatelessWidget {
  const CobroRecienteCard({super.key, required this.movimiento});

  final Movimiento movimiento;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final suave = tema.colorScheme.onSurfaceVariant;
    final vencido = movimiento.estado == 'vencido';
    final hora = _hora(movimiento.fechaMostrada);

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: TfSpace.s4,
          vertical: TfSpace.s3,
        ),
        child: Row(
          children: [
            TfIconoCanal(iconoCanal(movimiento.canal)),
            const SizedBox(width: TfSpace.s3),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    movimiento.conceptoVisible,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: tema.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '$hora · ${movimiento.etiquetaCanal}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: tema.textTheme.bodySmall?.copyWith(color: suave),
                  ),
                ],
              ),
            ),
            const SizedBox(width: TfSpace.s2),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 110),
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerRight,
                    child: Text(
                      movimiento.montoFormateado,
                      style: tema.textTheme.titleMedium?.copyWith(
                        fontFeatures: kTabular,
                        color: vencido ? suave : null,
                        decoration: vencido ? TextDecoration.lineThrough : null,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: TfSpace.s1),
                TfEstadoChip.desde(
                  estado: movimiento.estado,
                  etiqueta: movimiento.etiquetaEstado,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

IconData iconoCanal(String canal) {
  return switch (canal) {
    'qr_general' => Icons.qr_code_2_rounded,
    'qr_venta' => Icons.storefront_rounded,
    'notificacion' => Icons.phonelink_ring_rounded,
    _ => Icons.payment_rounded,
  };
}

String _hora(DateTime fecha) => horaCdmx(fecha);
