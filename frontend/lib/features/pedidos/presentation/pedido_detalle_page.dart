import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:cody/core/ui/tf_tokens.dart';

import '../data/clave_comando.dart';
import '../data/pedido.dart';
import '../data/pedido_repository.dart';
import 'pedido_providers.dart';
import 'widgets/renglon_editor.dart';
import 'widgets/pago_card.dart';
import 'widgets/entrega_card.dart';
import 'widgets/resumen_cotizacion_card.dart';

class PedidoDetallePage extends ConsumerStatefulWidget {
  const PedidoDetallePage({super.key, required this.id});
  final String id;
  @override
  ConsumerState<PedidoDetallePage> createState() => _PedidoDetallePageState();
}

class _PedidoDetallePageState extends ConsumerState<PedidoDetallePage> {
  final formulario = GlobalKey<FormState>();
  final claveRevision = ClaveComando();
  final clavePublicacion = ClaveComando();
  final claveCancelar = ClaveComando();
  final claveCobro = ClaveComando();
  final claveEspera = ClaveComando();
  final claveListo = ClaveComando();
  final claveEntregado = ClaveComando();
  final telefono = TextEditingController();
  final scroll = ScrollController();
  String canal = 'qr_venta';
  Timer? timer;
  bool permisoDenegado = false;
  bool cobroIncierto = false;
  bool cobroBloqueado = false;
  Pedido? pedido;
  String? aviso;
  String? errorTelefono;
  Map<String, dynamic> errores = {};
  bool ocupado = false;
  bool congelado = false;
  bool noAccesible = false;
  bool modificado = false;
  bool conflictoVersion = false;
  bool pendientes = false;
  int generacion = 0;
  @override
  void initState() {
    super.initState();
    cargar();
  }

  @override
  void dispose() {
    timer?.cancel();
    scroll.dispose();
    telefono.dispose();
    super.dispose();
  }

  void programarPolling() {
    timer?.cancel();
    if (pedido != null &&
        {
          'en_espera',
          'reservado',
          'enviando',
          'pendiente',
        }.contains(pedido!.pagoEstado)) {
      timer = Timer(
        const Duration(seconds: 2),
        () => cargar(conservarAviso: true, esPolling: true),
      );
    }
  }

  Future<void> cargar({
    bool conservarAviso = false,
    bool esPolling = false,
  }) async {
    if (ocupado) return;
    setState(() {
      ocupado = true;
    });
    try {
      final resultado = await ref
          .read(pedidoRepositoryProvider)
          .obtener(widget.id);
      if (!mounted) return;
      if (esPolling && modificado && pedido != null) {
        if (resultado.version != pedido!.version) {
          setState(() {
            conflictoVersion = true;
            aviso = 'El pedido cambió. Conservamos tu borrador; al recargar se perderán tus cambios.';
          });
        }
        return;
      }
      setState(() {
        pedido = resultado;
        conflictoVersion = false;
        generacion++;
        modificado = false;
        errores = {};
        noAccesible = false;
        permisoDenegado = false;
        if (!conservarAviso) aviso = null;
      });
      programarPolling();
    } on PedidoException catch (e) {
      if (mounted) {
        setState(() {
          aviso = e.mensaje;
          noAccesible = e.codigo == 'PEDIDO_NO_ACCESIBLE';
          permisoDenegado = e.status == 401 || e.status == 403;
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          ocupado = false;
        });
        if (!noAccesible && !permisoDenegado) programarPolling();
      }
    }
  }

  Future<void> operar({required bool publicar}) async {
    if (pedido == null) return;
    if (ocupado || congelado || conflictoVersion) {
      setState(() {
        aviso = ocupado
            ? 'Espera a que termine la operación actual.'
            : congelado
            ? 'Este pedido está congelado. Recarga para revisar su estado.'
            : 'El pedido cambió. Recarga antes de publicar la cotización.';
      });
      return;
    }
    if (!publicar && !(formulario.currentState?.validate() ?? false)) return;
    if (publicar && modificado) {
      setState(() {
        aviso = 'Guarda los cambios antes de publicar.';
      });
      return;
    }
    final contenido = <String, dynamic>{
      'expected_version': pedido!.version,
      if (!publicar)
        'renglones': pedido!.renglones.map((r) => r.toJson()).toList(),
    };
    final clave = publicar ? clavePublicacion : claveRevision;
    final cuerpo = {'command_key': clave.para(contenido), ...contenido};
    setState(() {
      ocupado = true;
      aviso = null;
      errores = {};
    });
    try {
      final repo = ref.read(pedidoRepositoryProvider);
      final resultado = publicar
          ? await repo.publicar(widget.id, cuerpo)
          : await repo.revisar(widget.id, cuerpo);
      if (!mounted) return;
      setState(() {
        pedido = resultado;
        generacion++;
        modificado = false;
        pendientes = false;
      });
      if (publicar) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (scroll.hasClients) scroll.jumpTo(0);
        });
      }
      clave.limpiar();
    } on PedidoException catch (e) {
      if (!mounted) return;
      setState(() {
        aviso = e.mensaje;
        errores = e.errores;
        pendientes = e.codigo == 'RENGLON_PENDIENTE';
        congelado = e.codigo == 'PEDIDO_CONGELADO';
        noAccesible = e.codigo == 'PEDIDO_NO_ACCESIBLE';
      });
      if (e.codigo == 'VERSION_OBSOLETA' || e.codigo == 'CLAVE_REUTILIZADA') {
        limpiarClaves();
        if (modificado) {
          setState(() {
            conflictoVersion = true;
            aviso = 'El pedido cambió. Conservamos tu borrador; al recargar se perderán tus cambios.';
          });
        } else {
          setState(() => ocupado = false);
          await cargar(conservarAviso: true);
        }
      }
    } finally {
      if (mounted) {
        setState(() {
          ocupado = false;
        });
      }
    }
  }

  void limpiarClaves() {
    claveRevision.limpiar();
    clavePublicacion.limpiar();
    claveCancelar.limpiar();
    claveCobro.limpiar();
    claveEspera.limpiar();
    claveListo.limpiar();
    claveEntregado.limpiar();
  }

  Future<void> accion(String tipo) async {
    if (pedido == null || ocupado) return;
    if (tipo == 'cobro' &&
        canal == 'notificacion' &&
        !RegExp(r'^\d{10}$').hasMatch(telefono.text.trim())) {
      setState(() => errorTelefono = 'El teléfono debe tener 10 dígitos.');
      return;
    }
    final clave = switch (tipo) {
      'cobro' => claveCobro,
      'espera' => claveEspera,
      'listo' => claveListo,
      _ => claveEntregado,
    };
    final contenido = <String, dynamic>{
      'expected_version': pedido!.version,
      if (tipo == 'cobro') ...{
        'accion': 'solicitar',
        'canal': canal,
        if (canal == 'notificacion')
          'telefono_bancario_confirmado': telefono.text.trim(),
      },
      if (tipo == 'espera') ...{
        'accion': 'activar_espera',
        'intento_id': pedido!.intento?['intento_id'],
      },
    };
    final cuerpo = {...contenido, 'command_key': clave.para(contenido)};
    setState(() {
      ocupado = true;
      aviso = null;
      errorTelefono = null;
    });
    try {
      final repo = ref.read(pedidoRepositoryProvider);
      final resultado = switch (tipo) {
        'cobro' || 'espera' => await repo.cobro(widget.id, cuerpo),
        'listo' => await repo.listo(widget.id, cuerpo),
        _ => await repo.entregado(widget.id, cuerpo),
      };
      if (!mounted) return;
      setState(() {
        pedido = resultado;
        cobroIncierto = false;
      });
      clave.limpiar();
      programarPolling();
    } on PedidoException catch (e) {
      if (!mounted) return;
      setState(() {
        aviso = e.mensaje;
        if (tipo == 'cobro' &&
            e.codigo == 'PAYLOAD_INVALIDO' &&
            canal == 'notificacion') {
          errorTelefono = 'Revisa el teléfono bancario.';
        }
        noAccesible = e.codigo == 'PEDIDO_NO_ACCESIBLE';
        permisoDenegado = e.status == 401 || e.status == 403;
        if (tipo == 'cobro' &&
            {
              'CUENTA_NO_ACTIVE',
              'MODO_CAMBIO',
              'ACEPTACION_REQUERIDA',
              'INTENCION_DISTINTA',
            }.contains(e.codigo)) {
          cobroBloqueado = true;
        }
      });
      if ((tipo == 'cobro' || tipo == 'espera') &&
          (e.status == null || e.status! >= 500) &&
          e.codigo != 'PROVEEDOR_NO_DISPONIBLE') {
        setState(() {
          cobroIncierto = true;
          aviso = 'No sabemos si se generó el cobro; no lo repitas.';
        });
      }
      if (e.codigo == 'VERSION_OBSOLETA' || e.codigo == 'CLAVE_REUTILIZADA') {
        limpiarClaves();
        if (modificado) {
          setState(() {
            conflictoVersion = true;
            aviso = 'El pedido cambió. Conservamos tu borrador; al recargar se perderán tus cambios.';
          });
        } else {
          setState(() => ocupado = false);
          await cargar(conservarAviso: true);
        }
      } else if (e.status != null && e.status! < 500) {
        clave.limpiar();
      }
    } finally {
      if (mounted) setState(() => ocupado = false);
    }
  }

  Future<void> cancelarPedido() async {
    final actual = pedido;
    if (actual == null || ocupado || conflictoVersion) return;
    final confirmado = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancelar pedido'),
        content: Text(
          '¿Cancelar el pedido #${actual.numero}? El cliente podrá enviar uno nuevo.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Volver'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Confirmar cancelación'),
          ),
        ],
      ),
    );
    if (confirmado != true || !mounted || pedido == null) return;
    final contenido = <String, dynamic>{'expected_version': pedido!.version};
    final cuerpo = {...contenido, 'command_key': claveCancelar.para(contenido)};
    setState(() {
      ocupado = true;
      aviso = null;
    });
    try {
      final resultado = await ref
          .read(pedidoRepositoryProvider)
          .cancelar(widget.id, cuerpo);
      if (!mounted) return;
      setState(() {
        pedido = resultado;
        modificado = false;
        generacion++;
        aviso = 'Pedido cancelado. El cliente puede enviar uno nuevo.';
      });
      claveCancelar.limpiar();
      programarPolling();
    } on PedidoException catch (e) {
      if (!mounted) return;
      setState(() => aviso = e.mensaje);
      if (e.codigo == 'VERSION_OBSOLETA') {
        claveCancelar.limpiar();
        setState(() => ocupado = false);
        await cargar(conservarAviso: true);
      } else if (e.status != null && e.status! < 500) {
        claveCancelar.limpiar();
      }
    } finally {
      if (mounted) setState(() => ocupado = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final actual = pedido;
    return Scaffold(
      appBar: AppBar(
        title: Text(actual == null ? 'Pedido' : 'Pedido #${actual.numero}'),
      ),
      body: SafeArea(
        top: false,
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: kMaxAnchoContenido),
            child: SingleChildScrollView(
              controller: scroll,
              child: ListView(
                shrinkWrap: true,
                primary: false,
                physics: const NeverScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(
                  kMargenPantalla,
                  TfSpace.s4,
                  kMargenPantalla,
                  TfSpace.s6,
                ),
                children: [
                if (ocupado)
                  LinearProgressIndicator(
                    color: Theme.of(context).colorScheme.secondary,
                  ),
                if (aviso != null)
                  Padding(
                    padding: const EdgeInsets.only(top: TfSpace.s3),
                    child: aviso!.contains('cancelado')
                        ? _AvisoExito(mensaje: aviso!)
                        : _AvisoError(
                            titulo: conflictoVersion
                                ? 'El pedido cambió'
                                : 'Revisa este pedido',
                            mensaje: aviso!,
                          ),
                  ),
                if (conflictoVersion)
                  OutlinedButton(
                    onPressed: ocupado ? null : cargar,
                    child: const Text('Recargar pedido'),
                  ),
                if (noAccesible)
                  OutlinedButton(
                    onPressed: () => context.go('/pedidos'),
                    child: const Text('Volver a pedidos'),
                  ),
                if (actual == null &&
                    !noAccesible &&
                    !permisoDenegado &&
                    !ocupado)
                  OutlinedButton(
                    onPressed: cargar,
                    child: const Text('Reintentar'),
                  ),
                if (actual != null && !noAccesible && !permisoDenegado) ...[
                  Text(
                    'Pedido #${actual.numero}',
                    style: Theme.of(context).textTheme.headlineLarge,
                  ),
                  const SizedBox(height: TfSpace.s1),
                  Text(
                    actual.cliente,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: TfSpace.s3),
                  if (actual.preparacion == 'listo')
                    const Text('Listo'),
                  if (actual.aceptado)
                    for (final renglon in actual.renglones)
                      Text(
                        'Solicitado: ${[
                          renglon.cantidadSolicitada,
                          renglon.unidadSolicitada,
                        ].whereType<String>().where((v) => v.isNotEmpty).join(' ').isEmpty ? renglon.solicitado : '${[
                          renglon.cantidadSolicitada,
                          renglon.unidadSolicitada,
                        ].whereType<String>().where((v) => v.isNotEmpty).join(' ')} · ${renglon.solicitado}'}',
                      ),
                  if (actual.cotizacion != null) ...[
                    ResumenCotizacionCard(
                      cotizacion: actual.cotizacion!,
                      aceptado: actual.aceptado,
                    ),
                    const SizedBox(height: TfSpace.s3),
                  ],
                  // Estas acciones se mantienen antes del editor: además de ser la
                  // jerarquía operativa de la pantalla, evita que queden fuera del
                  // área construida inicialmente en listas pequeñas.
                  PagoCard(
                    pedido: actual,
                    incierto: cobroIncierto,
                    errorTelefono: errorTelefono,
                    ocupado:
                        ocupado ||
                        conflictoVersion ||
                        cobroIncierto ||
                        cobroBloqueado,
                    telefono: telefono,
                    canal: canal,
                    cambiarCanal: (v) => setState(() => canal = v),
                    cobrar: () => accion('cobro'),
                    activar: () => accion('espera'),
                  ),
                  const SizedBox(height: TfSpace.s3),
                  EntregaCard(
                    pedido: actual,
                    ocupado: ocupado || conflictoVersion,
                    listo: () => accion('listo'),
                    entregado: () => accion('entregado'),
                  ),
                  const SizedBox(height: TfSpace.s4),
                  Form(
                    key: formulario,
                    child: Column(
                      children: [
                        for (var i = 0; i < actual.renglones.length; i++)
                          RenglonEditor(
                            key: ValueKey('$generacion-$i'),
                            renglon: actual.renglones[i],
                            indice: i,
                            editable: !ocupado && !congelado,
                            errores: errores,
                            resaltar:
                                pendientes &&
                                (actual.renglones[i].resolucion ==
                                        'pendiente' ||
                                    (errores['renglones_pendientes'] is List &&
                                        (errores['renglones_pendientes']
                                                as List)
                                            .contains(actual.renglones[i].id))),
                            alCambiar: () {
                              setState(() {
                                modificado = true;
                              });
                            },
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(height: TfSpace.s4),
                  if (!congelado) ...[
                    FilledButton(
                      onPressed: ocupado || conflictoVersion
                          ? null
                          : () => operar(publicar: false),
                      child: const Text('Guardar renglones'),
                    ),
                    const SizedBox(height: TfSpace.s2),
                    OutlinedButton(
                      onPressed: ocupado || conflictoVersion
                          ? null
                          : () => operar(publicar: true),
                      child: const Text('Publicar cotización'),
                    ),
                    const SizedBox(height: TfSpace.s2),
                  ],
                  if (actual.estado != 'cerrado')
                    OutlinedButton(
                      onPressed:
                          ocupado ||
                              conflictoVersion ||
                              (actual.cobroEnCurso ||
                                  actual.pagoEstado == 'pagado')
                          ? null
                          : cancelarPedido,
                      child: const Text('Cancelar pedido'),
                    ),
                ],
              ],
            ),
          ),
        ),
      ),
      ),
    );
  }
}

class _AvisoError extends StatelessWidget {
  const _AvisoError({required this.titulo, required this.mensaje});
  final String titulo;
  final String mensaje;

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(TfSpace.s4),
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.errorContainer,
      borderRadius: BorderRadius.circular(TfRadius.md),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(titulo, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: TfSpace.s1),
        Text(mensaje),
      ],
    ),
  );
}

class _AvisoExito extends StatelessWidget {
  const _AvisoExito({required this.mensaje});
  final String mensaje;
  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(TfSpace.s4),
      decoration: BoxDecoration(
        color: t.colorScheme.tertiaryContainer,
        borderRadius: BorderRadius.circular(TfRadius.md),
      ),
      child: Row(
        children: [
          Icon(
            Icons.check_circle_rounded,
            color: t.colorScheme.onTertiaryContainer,
          ),
          const SizedBox(width: TfSpace.s2),
          Expanded(
            child: Text(
              mensaje,
              style: t.textTheme.bodyMedium?.copyWith(
                color: t.colorScheme.onTertiaryContainer,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
