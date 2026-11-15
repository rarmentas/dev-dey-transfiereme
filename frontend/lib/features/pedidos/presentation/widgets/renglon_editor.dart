import 'package:flutter/material.dart';

import 'package:cody/core/ui/tf_tokens.dart';

import '../../data/pedido.dart';

class RenglonEditor extends StatelessWidget {
  const RenglonEditor({
    super.key,
    required this.renglon,
    required this.indice,
    required this.editable,
    required this.errores,
    required this.alCambiar,
    this.resaltar = false,
  });
  final Renglon renglon;
  final int indice;
  final bool editable;
  final Map<String, dynamic> errores;
  final VoidCallback alCambiar;
  final bool resaltar;

  String? error(String campo) {
    final valor = errores['renglones.$indice.$campo'];
    return valor is List && valor.isNotEmpty ? valor.first.toString() : null;
  }

  @override
  Widget build(BuildContext context) {
    final incluido = renglon.resolucion == 'incluido';
    final cantidadSolicitada = [
      renglon.cantidadSolicitada,
      renglon.unidadSolicitada,
    ].whereType<String>().where((valor) => valor.isNotEmpty).join(' ');
    final solicitado = cantidadSolicitada.isEmpty
        ? renglon.solicitado
        : '$cantidadSolicitada · ${renglon.solicitado}';
    return Card(
      color: resaltar ? Theme.of(context).colorScheme.errorContainer : null,
      child: Padding(
        padding: const EdgeInsets.all(TfSpace.s4),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Artículo solicitado',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: TfSpace.s1),
            Text(
              'Solicitado: $solicitado',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            if (resaltar) ...[
              const SizedBox(height: TfSpace.s3),
              Row(
                children: [
                  Icon(
                    Icons.error_rounded,
                    color: Theme.of(context).colorScheme.onErrorContainer,
                  ),
                  const SizedBox(width: TfSpace.s2),
                  Expanded(
                    child: Text(
                      'Revisa este artículo para publicar la cotización',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context).colorScheme.onErrorContainer,
                      ),
                    ),
                  ),
                ],
              ),
            ],
            const SizedBox(height: TfSpace.s4),
            DropdownButtonFormField<String>(
              initialValue: renglon.resolucion,
              decoration: InputDecoration(
                labelText: '¿Se incluye en el pedido?',
                errorText: error('resolucion'),
                errorMaxLines: 3,
              ),
              items: const [
                DropdownMenuItem(
                  value: 'pendiente',
                  child: Text('Por revisar'),
                ),
                DropdownMenuItem(value: 'incluido', child: Text('Incluir')),
                DropdownMenuItem(
                  value: 'excluido',
                  child: Text('No disponible'),
                ),
              ],
              onChanged: editable
                  ? (v) {
                      renglon.resolucion = v!;
                      alCambiar();
                    }
                  : null,
            ),
            const SizedBox(height: TfSpace.s4),
            TextFormField(
              initialValue: renglon.descripcion,
              enabled: editable,
              maxLength: 200,
              decoration: InputDecoration(
                labelText: 'Descripción',
                errorText: error('descripcion'),
                errorMaxLines: 3,
              ),
              onChanged: (v) {
                renglon.descripcion = v;
                alCambiar();
              },
              validator: (v) => incluido && (v == null || v.trim().isEmpty)
                  ? 'Escribe una descripción.'
                  : null,
            ),
            const SizedBox(height: TfSpace.s4),
            TextFormField(
              initialValue: renglon.cantidad,
              enabled: editable,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: InputDecoration(
                labelText: 'Cantidad',
                errorText: error('cantidad'),
                errorMaxLines: 3,
              ),
              onChanged: (v) {
                renglon.cantidad = v.trim();
                alCambiar();
              },
              validator: (v) {
                final s = v?.trim() ?? '';
                if (s.isEmpty && !incluido) return null;
                if (!RegExp(r'^\d{1,4}(\.\d{1,3})?$').hasMatch(s) ||
                    (double.tryParse(s) ?? 0) <= 0 ||
                    (double.tryParse(s) ?? 0) > 9999.999) {
                  return 'Usa una cantidad positiva con hasta 3 decimales.';
                }
                return null;
              },
            ),
            const SizedBox(height: TfSpace.s4),
            TextFormField(
              initialValue: renglon.unidad,
              enabled: editable,
              maxLength: 30,
              decoration: InputDecoration(
                labelText: 'Unidad (opcional)',
                errorText: error('unidad'),
                errorMaxLines: 3,
              ),
              onChanged: (v) {
                renglon.unidad = v;
                alCambiar();
              },
            ),
            const SizedBox(height: TfSpace.s4),
            TextFormField(
              initialValue: renglon.precio == null
                  ? ''
                  : '${renglon.precio! ~/ 100}.${(renglon.precio! % 100).toString().padLeft(2, '0')}',
              enabled: editable,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: InputDecoration(
                labelText: 'Precio unitario en pesos',
                helperText: 'Pesos mexicanos, por ejemplo 12.50',
                prefixText: r'$ ',
                errorText: error('precio_unitario_centavos'),
                errorMaxLines: 3,
                helperMaxLines: 3,
              ),
              onChanged: (v) {
                renglon.precio = precioCentavos(v);
                alCambiar();
              },
              validator: (v) {
                if ((v?.trim().isEmpty ?? true) && !incluido) return null;
                return precioCentavos(v ?? '') == null
                    ? 'Usa un precio positivo con hasta 2 decimales.'
                    : null;
              },
            ),
            const SizedBox(height: TfSpace.s4),
            TextFormField(
              initialValue: renglon.motivo,
              enabled: editable,
              maxLength: 200,
              decoration: InputDecoration(
                labelText: '¿Por qué no está disponible?',
                errorText: error('motivo_exclusion'),
                errorMaxLines: 3,
              ),
              onChanged: (v) {
                renglon.motivo = v;
                alCambiar();
              },
              validator: (v) =>
                  renglon.resolucion == 'excluido' &&
                      (v == null || v.trim().isEmpty)
                  ? 'Escribe el motivo.'
                  : null,
            ),
            if (renglon.subtotal != null)
              Padding(
                padding: const EdgeInsets.only(top: TfSpace.s3),
                child: Text(
                  'Subtotal guardado: ${formatearCentavos(renglon.subtotal!)}',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
          ],
        ),
      ),
    );
  }
}

int? precioCentavos(String valor) {
  final texto = valor.trim();
  if (!RegExp(r'^\d{1,15}(\.\d{1,2})?$').hasMatch(texto)) return null;
  final partes = texto.split('.');
  final centavos =
      int.parse(partes[0]) * 100 +
      int.parse((partes.length > 1 ? partes[1] : '').padRight(2, '0'));
  return centavos > 0 && centavos <= _maxCentavosSeguroWeb ? centavos : null;
}

/// Mayor entero exacto en JavaScript (2^53 - 1); la app compila a web.
const int _maxCentavosSeguroWeb = 9007199254740991;
