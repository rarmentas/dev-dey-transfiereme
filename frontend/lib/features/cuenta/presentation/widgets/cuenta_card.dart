import 'package:flutter/material.dart';

import '../../../../core/ui/ui.dart';
import '../../../../theme/transfiereme_theme.dart';
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
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final estadoRegistro = _estadoRegistro(cuenta.registro);
    final estaActiva = cuenta.puedeCobrar;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(TfSpace.s4),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(cuenta.clabe, style: tema.textTheme.titleMedium),
                ),
                if (cuenta.predeterminada)
                  const Padding(
                    padding: EdgeInsets.only(left: TfSpace.s2),
                    child: _CuentaPredeterminada(),
                  ),
              ],
            ),
            const SizedBox(height: TfSpace.s3),
            Wrap(
              spacing: TfSpace.s2,
              runSpacing: TfSpace.s2,
              children: [
                _EtiquetaCuenta(estadoRegistro),
                _EtiquetaCuenta(estaActiva ? 'Activa' : 'Pendiente de activación'),
              ],
            ),
            const SizedBox(height: TfSpace.s3),
            Text(
              cuenta.sincronizadaEn == null || cuenta.sincronizadaEn!.isEmpty
                  ? 'Última sincronización: sin datos'
                  : 'Última sincronización: ${cuenta.sincronizadaEn}',
              style: tema.textTheme.bodySmall,
            ),
            if (cuenta.ultimoError.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: TfSpace.s1),
                child: Text(
                  'Última consulta: ${cuenta.ultimoError}',
                  style: tema.textTheme.bodySmall,
                ),
              ),
            if (cuenta.anomalia.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: TfSpace.s1),
                child: Text(
                  'Anomalía: ${cuenta.anomalia}',
                  style: tema.textTheme.bodySmall,
                ),
              ),
            if (cuenta.operacionEstado == 'pendiente' ||
                cuenta.operacionEstado == 'en_curso')
              Padding(
                padding: const EdgeInsets.only(top: TfSpace.s3),
                child: _OperacionEnCurso(cuenta: cuenta),
              ),
            if (registroIncierto ||
                cuenta.registro == 'incierto' ||
                cuenta.registro == 'registrando')
              Padding(
                padding: const EdgeInsets.only(top: TfSpace.s3),
                child: Text(
                  'Registro sin confirmar. No lo repitas.',
                  style: tema.textTheme.bodyMedium?.copyWith(
                    color:
                        Theme.of(context).extension<TfColors>()?.pendingText ??
                        Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            const SizedBox(height: TfSpace.s4),
            Wrap(
              spacing: 8,
              runSpacing: TfSpace.s2,
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

  String _estadoRegistro(String registro) => switch (registro) {
    'sin_registro' => 'Sin registrar',
    'registrando' => 'Registro en proceso',
    'registrado' => 'Registrada',
    'incierto' => 'Sin confirmar',
    'rechazado' => 'Registro rechazado',
    _ => 'Estado no disponible',
  };
}

class _EtiquetaCuenta extends StatelessWidget {
  const _EtiquetaCuenta(this.texto);
  final String texto;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: TfSpace.s2, vertical: TfSpace.s1),
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      borderRadius: BorderRadius.circular(999),
    ),
    child: Text(texto, style: Theme.of(context).textTheme.labelMedium),
  );
}

class _CuentaPredeterminada extends StatelessWidget {
  const _CuentaPredeterminada();
  @override
  Widget build(BuildContext context) => Semantics(
    label: 'Cuenta predeterminada',
    child: Tooltip(
      message: 'Cuenta predeterminada',
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.star_rounded, color: Theme.of(context).colorScheme.primary, size: TfSize.icon),
          const SizedBox(width: 2),
          const Text('Por defecto'),
        ],
      ),
    ),
  );
}

class _OperacionEnCurso extends StatelessWidget {
  const _OperacionEnCurso({required this.cuenta});
  final CuentaCobro cuenta;
  @override
  Widget build(BuildContext context) {
    final color =
        Theme.of(context).extension<TfColors>()?.pending ??
        Theme.of(context).colorScheme.primary;
    final texto =
        '${cuenta.operacionTipo == 'sync' ? 'Sincronización' : 'Registro'} ${cuenta.operacionEstado == 'pendiente' ? 'pendiente' : 'en curso'}';
    return Semantics(
      label: texto,
      child: Row(
        children: [
          Icon(Icons.hourglass_top_rounded, color: color, size: 18),
          const SizedBox(width: TfSpace.s2),
          Expanded(
            child: Text(texto, style: Theme.of(context).textTheme.bodyMedium),
          ),
        ],
      ),
    );
  }
}
