import 'package:flutter/material.dart';

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
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(switch (pedido.preparacion) {
            'listo' => 'Listo',
            'entregado' => 'Entregado',
            _ => 'Preparación pendiente',
          }),
          if (pedido.entrega['listo_en'] != null)
            Text(
              'Listo: ${pedido.entrega['listo_por'] ?? ''} · ${pedido.entrega['listo_en']}',
            ),
          if (pedido.entrega['entregado_en'] != null)
            Text(
              'Entregado: ${pedido.entrega['entregado_por'] ?? ''} · ${pedido.entrega['entregado_en']}',
            ),
          if (pedido.preparacion == 'pendiente')
            FilledButton(
              onPressed: !ocupado && pedido.pagoEstado == 'pagado'
                  ? listo
                  : null,
              child: const Text('Marcar listo'),
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
