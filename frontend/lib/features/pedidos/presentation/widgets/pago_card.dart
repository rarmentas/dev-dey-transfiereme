import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../data/pedido.dart';

class PagoCard extends StatelessWidget {
  const PagoCard({
    super.key,
    required this.pedido,
    required this.ocupado,
    required this.cobrar,
    required this.activar,
    required this.telefono,
    required this.canal,
    required this.cambiarCanal,
    this.incierto = false,
    this.errorTelefono,
  });
  final Pedido pedido;
  final bool ocupado, incierto;
  final String? errorTelefono;
  final VoidCallback cobrar, activar;
  final TextEditingController telefono;
  final String canal;
  final ValueChanged<String> cambiarCanal;
  @override
  Widget build(BuildContext context) {
    final estado = pedido.pagoEstado;
    final intento = pedido.intento;
    final texto = switch (estado) {
      'en_espera' => 'Cobro en espera',
      'reservado' || 'enviando' => 'Generando cobro…',
      'pendiente' => 'Pago pendiente',
      'incierto' => 'Cobro no confirmado. No lo repitas.',
      'pagado' => 'Pagado',
      'descartado' => 'Cobro descartado. Publica y acepta de nuevo.',
      'rechazado' => 'Cobro rechazado',
      'vencido' => 'Cobro vencido',
      _ => 'Sin cobro',
    };
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(texto),
            if (estado == 'pendiente' &&
                intento?['qr'] is String &&
                (intento!['qr'] as String).isNotEmpty)
              SizedBox(
                width: 200,
                height: 200,
                child: QrImageView(data: intento['qr'] as String),
              ),
            if (estado == 'pendiente' && intento?['vencimiento'] != null)
              Text('Vence: ${intento!['vencimiento']}'),
            if (estado == 'en_espera' && !incierto)
              FilledButton(
                onPressed: ocupado ? null : activar,
                child: const Text('Activar cobro'),
              ),
            if (estado == 'sin_cobro' && pedido.aceptado && !incierto) ...[
              DropdownButton<String>(
                value: canal,
                items: const [
                  DropdownMenuItem(value: 'qr_venta', child: Text('Código QR')),
                  DropdownMenuItem(
                    value: 'notificacion',
                    child: Text('Enviar al celular'),
                  ),
                ],
                onChanged: ocupado ? null : (v) => cambiarCanal(v!),
              ),
              if (canal == 'notificacion')
                TextField(
                  controller: telefono,
                  enabled: !ocupado,
                  keyboardType: TextInputType.phone,
                  decoration: InputDecoration(
                    labelText: 'Teléfono bancario (10 dígitos)',
                    errorText: errorTelefono,
                  ),
                ),
              FilledButton(
                onPressed: ocupado ? null : cobrar,
                child: const Text('Cobrar'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
