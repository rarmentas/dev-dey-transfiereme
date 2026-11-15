import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';

import 'package:cody/core/ui/tf_tokens.dart';

import 'pedido_estado_chip.dart';

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
    final previo = intento?['aceptacion_id'];
    final deOtraAceptacion =
        pedido.aceptado &&
        previo is String &&
        previo != pedido.aceptacionId &&
        const {'descartado', 'rechazado', 'vencido'}.contains(estado);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(TfSpace.s4),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Pago', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: TfSpace.s2),
            PedidoEstadoChip.pago(
              estado: incierto
                  ? 'incierto'
                  : (deOtraAceptacion ? 'sin_cobro' : estado),
            ),
            if (incierto) ...[
              const SizedBox(height: TfSpace.s3),
              _AvisoCobroIncierto(),
            ],
            if (deOtraAceptacion)
              Text('Cobro anterior: ${etiquetaPago(estado)}'),
            if (estado == 'pendiente' &&
                intento?['qr'] is String &&
                (intento!['qr'] as String).isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: TfSpace.s4),
                child: Center(
                  child: Container(
                    padding: const EdgeInsets.all(TfSpace.s4),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(TfRadius.xl),
                    ),
                    child: Semantics(
                      label: 'Código QR para pagar este pedido',
                      image: true,
                      child: SizedBox(
                        width: TfSize.qrScreen,
                        height: TfSize.qrScreen,
                        child: QrImageView(
                          data: intento['qr'] as String,
                          backgroundColor: Colors.white,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            if (estado == 'pendiente' && intento?['qr'] is String)
              Padding(
                padding: const EdgeInsets.only(top: TfSpace.s3),
                child: Text(
                  'Pídele que escanee con la app de su banco',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ),
            if (estado == 'pendiente' && intento?['vencimiento'] != null)
              Text('Vence: ${intento!['vencimiento']}'),
            if (estado == 'en_espera' && !incierto)
              FilledButton(
                onPressed: ocupado ? null : activar,
                child: const Text('Activar cobro'),
              ),
            if ((estado == 'sin_cobro' || deOtraAceptacion) &&
                pedido.aceptado &&
                !incierto) ...[
              DropdownButtonFormField<String>(
                initialValue: canal,
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: 'Cómo recibirá el cobro',
                ),
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
              const SizedBox(height: TfSpace.s4),
              SizedBox(
                width: double.infinity,
                height: TfSize.buttonXl,
                child: FilledButton.icon(
                  onPressed: ocupado ? null : cobrar,
                  icon: const Icon(Icons.payments_rounded),
                  label: const Text('Cobrar'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _AvisoCobroIncierto extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Semantics(
      liveRegion: true,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(TfSpace.s3),
        decoration: BoxDecoration(
          color: t.colorScheme.secondaryContainer,
          borderRadius: BorderRadius.circular(TfRadius.md),
        ),
        child: Row(
          children: [
            Icon(
              Icons.warning_amber_rounded,
              color: t.colorScheme.onSecondaryContainer,
            ),
            const SizedBox(width: TfSpace.s2),
            Expanded(
              child: Text(
                'Cobro sin confirmar. No lo repitas.',
                style: t.textTheme.bodyMedium?.copyWith(
                  color: t.colorScheme.onSecondaryContainer,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
