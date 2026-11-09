import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/app_router.dart';
import '../../../../core/ui/ui.dart';
import '../../data/cuenta_estado.dart';
import '../cuenta_pey_mensajes.dart';
import '../cuenta_providers.dart';

/// Tarjeta de estado de cuenta pey para Ajustes e Inicio.
String _resumenActivo(EstadoCuentaPey estado) {
  final partes = <String>[];
  if (estado.clabeEnmascarada.isNotEmpty) {
    partes.add('CLABE ${estado.clabeEnmascarada}');
  }
  if (estado.peyBankAccountIdSufijo.isNotEmpty) {
    partes.add('…${estado.peyBankAccountIdSufijo}');
  }
  return partes.isEmpty ? 'Lista para cobrar' : partes.join(' · ');
}

class CuentaPeyEstadoCard extends ConsumerWidget {
  const CuentaPeyEstadoCard({super.key, this.compacto = false});

  /// En Inicio usa menos texto y sin borde de lista.
  final bool compacto;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final estadoAsync = ref.watch(cuentaEstadoProvider);
    final tema = Theme.of(context);

    return estadoAsync.when(
      skipLoadingOnRefresh: false,
      data: (estado) {
        if (estado.puedeCobrar && !compacto) {
          return Card(
            margin: EdgeInsets.zero,
            child: ListTile(
              leading: Icon(
                Icons.verified_rounded,
                color: tema.colorScheme.primary,
              ),
              title: Text(etiquetaFase(estado)),
              subtitle: Text(
                _resumenActivo(estado),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          );
        }
        if (estado.puedeCobrar && compacto) {
          return const SizedBox.shrink();
        }
        return Card(
          margin: EdgeInsets.zero,
          child: Padding(
            padding: const EdgeInsets.all(TfSpace.s5),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Cuenta para cobrar',
                  style: tema.textTheme.titleMedium,
                ),
                const SizedBox(height: TfSpace.s2),
                Text(
                  etiquetaFase(estado),
                  style: tema.textTheme.bodyLarge?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (detalleCuentaPey(estado) != etiquetaFase(estado))
                  Padding(
                    padding: const EdgeInsets.only(top: TfSpace.s1),
                    child: Text(
                      detalleCuentaPey(estado),
                      style: tema.textTheme.bodyMedium?.copyWith(
                        color: tema.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                if (!compacto && estado.paso != 3) ...[
                  const SizedBox(height: TfSpace.s2),
                  Text(
                    mensajeSiguientePaso(estado),
                    style: tema.textTheme.bodySmall?.copyWith(
                      color: tema.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
                const SizedBox(height: TfSpace.s4),
                if (estado.paso == 1)
                  FilledButton(
                    key: const Key('cta_registrar_clabe_estado'),
                    onPressed: () => _irRegistrarClabe(ref, context),
                    child: const Text('Registrar CLABE'),
                  )
                else if (estado.paso == 2) ...[
                  FilledButton(
                    key: const Key('cta_registro_pey'),
                    onPressed: () => context.push(kRutaRegistrarCuentaPey),
                    child: const Text('Registrar en pey'),
                  ),
                ] else if (estado.paso == 3) ...[
                  OutlinedButton.icon(
                    key: const Key('boton_verificar_activacion'),
                    onPressed: () => _abrirVerificacion(ref, context, estado),
                    icon: const Icon(Icons.info_outline_rounded, size: 20),
                    label: const Text('Verificar'),
                  ),
                ],
              ],
            ),
          ),
        );
      },
      loading: () => Card(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.all(TfSpace.s5),
          child: Row(
            children: [
              const SizedBox(
                width: 24,
                height: 24,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
              const SizedBox(width: TfSpace.s3),
              Expanded(
                child: Text(
                  'Cargando estado de cuenta…',
                  style: tema.textTheme.bodyMedium,
                ),
              ),
            ],
          ),
        ),
      ),
      error: (error, _) => Card(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.all(TfSpace.s5),
          child: TfAvisoError(
            titulo: 'No pudimos cargar el estado de tu cuenta',
            mensaje: error.toString(),
            accion: OutlinedButton(
              onPressed: () => ref.invalidate(cuentaEstadoProvider),
              child: const Text('Reintentar'),
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _irRegistrarClabe(WidgetRef ref, BuildContext context) async {
    await context.push(kRutaRegistrarClabe);
    ref.invalidate(cuentaEstadoProvider);
  }

  Future<void> _abrirVerificacion(
    WidgetRef ref,
    BuildContext context,
    EstadoCuentaPey estado,
  ) async {
    final activo = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return _DialogoActivacionClabe(
          estado: estado,
          onRevisar: () => ref.read(cuentaEstadoRepositoryProvider).sincronizar(),
        );
      },
    );
    if (!context.mounted || activo != true) {
      if (activo == false) {
        ref.invalidate(cuentaEstadoProvider);
      }
      return;
    }
    ref.invalidate(cuentaEstadoProvider);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Tu cuenta ya está activa para cobrar.')),
    );
  }
}

class _DialogoActivacionClabe extends StatefulWidget {
  const _DialogoActivacionClabe({
    required this.estado,
    required this.onRevisar,
  });

  final EstadoCuentaPey estado;
  final Future<EstadoCuentaPey> Function() onRevisar;

  @override
  State<_DialogoActivacionClabe> createState() => _DialogoActivacionClabeState();
}

class _DialogoActivacionClabeState extends State<_DialogoActivacionClabe> {
  var _revisando = false;
  String? _error;

  Future<void> _revisar() async {
    if (_revisando) {
      return;
    }
    setState(() {
      _revisando = true;
      _error = null;
    });
    try {
      final estado = await widget.onRevisar();
      if (!mounted) {
        return;
      }
      Navigator.of(context).pop(estado.puedeCobrar);
    } on CuentaPeyApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _revisando = false;
        _error = error.mensaje;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _revisando = false;
        _error = 'No pudimos sincronizar. Inténtalo de nuevo.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return AlertDialog(
      title: const Text('Activación de tu CLABE'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              mensajeActivacionClabe(widget.estado),
              style: tema.textTheme.bodyLarge,
            ),
            if (_error != null) ...[
              const SizedBox(height: TfSpace.s3),
              Text(
                _error!,
                style: tema.textTheme.bodyMedium?.copyWith(
                  color: tema.colorScheme.error,
                ),
              ),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          key: const Key('cerrar_activacion_clabe'),
          onPressed: _revisando ? null : () => Navigator.of(context).pop(),
          child: const Text('Cerrar'),
        ),
        FilledButton(
          key: const Key('revisar_estado_activacion'),
          onPressed: _revisando ? null : _revisar,
          child: Text(_revisando ? 'Revisando…' : 'Revisar estado'),
        ),
      ],
    );
  }
}
