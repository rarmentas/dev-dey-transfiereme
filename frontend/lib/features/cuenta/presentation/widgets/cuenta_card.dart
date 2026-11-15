import 'package:flutter/material.dart';

import '../../data/cuenta_cobro.dart';

class CuentaCard extends StatelessWidget {
  const CuentaCard({
    super.key,
    required this.cuenta,
    required this.ocupado,
    this.registroIncierto = false,
    required this.registrar,
    required this.sincronizar,
    required this.elegir,
  });
  final CuentaCobro cuenta;
  final bool ocupado, registroIncierto;
  final VoidCallback registrar, sincronizar, elegir;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(cuenta.clabe),
          Text(
            '${cuenta.predeterminada ? 'Por defecto · ' : ''}Registro: ${switch (cuenta.registro) {
              'sin_registro' => 'Sin registro',
              'registrando' => 'En proceso',
              'registrado' => 'Registrada',
              'incierto' => 'Sin confirmar',
              'rechazado' => 'Rechazada',
              _ => 'Desconocido',
            }} · Estado conocido: ${cuenta.status == 'active' ? 'Activa' : 'Pendiente'}',
          ),
          Text(
            cuenta.sincronizadaEn == null || cuenta.sincronizadaEn!.isEmpty
                ? 'Última sincronización: sin datos'
                : 'Última sincronización: ${cuenta.sincronizadaEn}',
          ),
          if (cuenta.ultimoError.isNotEmpty)
            Text('Última consulta: ${cuenta.ultimoError}'),
          if (cuenta.anomalia.isNotEmpty) Text('Anomalía: ${cuenta.anomalia}'),
          if (cuenta.operacionEstado == 'pendiente' ||
              cuenta.operacionEstado == 'en_curso')
            Text(
              '${cuenta.operacionTipo == 'sync' ? 'Sincronización' : 'Registro'} '
              '${cuenta.operacionEstado == 'pendiente' ? 'pendiente' : 'en curso'}',
            ),
          if (registroIncierto ||
              cuenta.registro == 'incierto' ||
              cuenta.registro == 'registrando')
            const Text('Registro sin confirmar. No lo repitas.'),
          Wrap(
            spacing: 8,
            children: [
              if (!registroIncierto &&
                  (cuenta.registro == 'sin_registro' ||
                      cuenta.registro == 'rechazado'))
                OutlinedButton(
                  onPressed: ocupado ? null : registrar,
                  child: const Text('Registrar'),
                ),
              if (registroIncierto || cuenta.registro != 'sin_registro')
                OutlinedButton(
                  onPressed: ocupado ? null : sincronizar,
                  child: const Text('Sincronizar'),
                ),
              if (!cuenta.predeterminada && cuenta.puedeCobrar)
                OutlinedButton(
                  onPressed: ocupado ? null : elegir,
                  child: const Text('Elegir por defecto'),
                ),
            ],
          ),
        ],
      ),
    ),
  );
}
