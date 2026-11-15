import 'package:flutter/material.dart';

import 'package:cody/core/ui/tf_tokens.dart';

import '../../data/pedido.dart';

class ResumenCotizacionCard extends StatelessWidget {
  const ResumenCotizacionCard({
    super.key,
    required this.cotizacion,
    required this.aceptado,
  });
  final Cotizacion cotizacion;
  final bool aceptado;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(TfSpace.s4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Cotización', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: TfSpace.s2),
          Text(
            'Total comercial: ${formatearCentavos(cotizacion.total)}',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
          if (cotizacion.demo)
            Padding(
              padding: const EdgeInsets.only(top: TfSpace.s3),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(TfSpace.s3),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(TfRadius.md),
                ),
                child: Text(
                  'En demo se cobrará ${formatearCentavos(cotizacion.efectivo)}',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onPrimaryContainer,
                  ),
                ),
              ),
            ),
          const SizedBox(height: TfSpace.s3),
          Text(
            'Revisión ${cotizacion.revision}',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
          if (aceptado)
            Text(
              'Aceptada por el cliente (ACEPTAR ${cotizacion.token})',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          const Text('Cobro: no habilitado todavía'),
        ],
      ),
    ),
  );
}
