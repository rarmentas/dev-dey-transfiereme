import 'package:flutter/material.dart';

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
    return Card(
      color: resaltar ? Theme.of(context).colorScheme.errorContainer : null,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Solicitado: ${renglon.solicitado}'),
            DropdownButtonFormField<String>(
              initialValue: renglon.resolucion,
              decoration: InputDecoration(
                labelText: 'Resolución',
                errorText: error('resolucion'),
              ),
              items: const [
                DropdownMenuItem(value: 'pendiente', child: Text('Pendiente')),
                DropdownMenuItem(value: 'incluido', child: Text('Incluir')),
                DropdownMenuItem(value: 'excluido', child: Text('Excluir')),
              ],
              onChanged: editable
                  ? (v) {
                      renglon.resolucion = v!;
                      alCambiar();
                    }
                  : null,
            ),
            TextFormField(
              initialValue: renglon.descripcion,
              enabled: editable,
              maxLength: 200,
              decoration: InputDecoration(
                labelText: 'Descripción',
                errorText: error('descripcion'),
              ),
              onChanged: (v) {
                renglon.descripcion = v;
                alCambiar();
              },
              validator: (v) => incluido && (v == null || v.trim().isEmpty)
                  ? 'Escribe una descripción.'
                  : null,
            ),
            TextFormField(
              initialValue: renglon.cantidad,
              enabled: editable,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: InputDecoration(
                labelText: 'Cantidad',
                errorText: error('cantidad'),
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
            TextFormField(
              initialValue: renglon.unidad,
              enabled: editable,
              maxLength: 30,
              decoration: InputDecoration(
                labelText: 'Unidad (opcional)',
                errorText: error('unidad'),
              ),
              onChanged: (v) {
                renglon.unidad = v;
                alCambiar();
              },
            ),
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
                errorText: error('precio_unitario_centavos'),
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
            TextFormField(
              initialValue: renglon.motivo,
              enabled: editable,
              maxLength: 200,
              decoration: InputDecoration(
                labelText: 'Motivo de exclusión',
                errorText: error('motivo_exclusion'),
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
              Text('Subtotal: ${formatearCentavos(renglon.subtotal!)}'),
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
  return centavos > 0 && centavos <= 9223372036854775807 ? centavos : null;
}
