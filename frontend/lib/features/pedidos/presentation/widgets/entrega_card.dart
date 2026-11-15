import 'package:flutter/material.dart';

import 'package:cody/core/ui/tf_tokens.dart';

import 'pedido_estado_chip.dart';

import '../../data/pedido.dart';

class EntregaCard extends StatelessWidget {
  const EntregaCard({
    super.key,
    required this.pedido,
    required this.ocupado,
    required this.listo,
    required this.entregado,
  });
  final Pedido pedido;
  final bool ocupado;
  final VoidCallback listo, entregado;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(TfSpace.s4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Entrega', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: TfSpace.s2),
          PedidoEstadoChip.preparacion(estado: pedido.preparacion),
          if (pedido.entrega['listo_en'] != null)
            Text(
              'Listo: ${pedido.entrega['listo_por'] ?? ''} · ${pedido.entrega['listo_en']}',
            ),
          if (pedido.entrega['entregado_en'] != null)
            Text(
              'Entregado: ${pedido.entrega['entregado_por'] ?? ''} · ${pedido.entrega['entregado_en']}',
            ),
          if (pedido.preparacion == 'pendiente')
            Padding(
              padding: const EdgeInsets.only(top: TfSpace.s4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (pedido.pagoEstado != 'pagado')
                    Text(
                      'Primero confirma el pago',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  FilledButton(
                    onPressed: !ocupado && pedido.pagoEstado == 'pagado'
                        ? listo
                        : null,
                    child: const Text('Marcar listo'),
                  ),
                ],
              ),
            ),
          if (pedido.preparacion == 'listo')
            FilledButton(
              onPressed: ocupado ? null : entregado,
              child: const Text('Marcar entregado'),
            ),
        ],
      ),
    ),
  );
}
