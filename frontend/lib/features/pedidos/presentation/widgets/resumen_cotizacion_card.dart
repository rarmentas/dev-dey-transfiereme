import 'package:flutter/material.dart';

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
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Cotización · revisión ${cotizacion.revision}'),
          Text('Total comercial: ${formatearCentavos(cotizacion.total)}'),
          if (cotizacion.demo)
            Text(
              'En demo se cobrará ${formatearCentavos(cotizacion.efectivo)}',
            ),
          if (aceptado)
            Text('Aceptada por el cliente (ACEPTAR ${cotizacion.token})'),
          const Text('Cobro: no habilitado todavía'),
        ],
      ),
    ),
  );
}
