import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../data/clave_comando.dart';
import '../data/pedido.dart';
import '../data/pedido_repository.dart';
import 'pedido_providers.dart';
import 'widgets/renglon_editor.dart';
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
  Pedido? pedido;
  String? aviso;
  Map<String, dynamic> errores = {};
  bool ocupado = false;
  bool congelado = false;
  bool noAccesible = false;
  bool modificado = false;
  bool pendientes = false;
  int generacion = 0;
  @override
  void initState() {
    super.initState();
    cargar();
  }

  Future<void> cargar({bool conservarAviso = false}) async {
    setState(() {
      ocupado = true;
    });
    try {
      final resultado = await ref
          .read(pedidoRepositoryProvider)
          .obtener(widget.id);
      if (!mounted) return;
      setState(() {
        pedido = resultado;
        generacion++;
        modificado = false;
        errores = {};
        noAccesible = false;
        if (!conservarAviso) aviso = null;
      });
    } on PedidoException catch (e) {
      if (mounted) {
        setState(() {
          aviso = e.mensaje;
          noAccesible = e.codigo == 'PEDIDO_NO_ACCESIBLE';
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          ocupado = false;
        });
      }
    }
  }

  Future<void> operar({required bool publicar}) async {
    if (pedido == null || ocupado || congelado) return;
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
        claveRevision.limpiar();
        clavePublicacion.limpiar();
        await cargar(conservarAviso: true);
      }
    } finally {
      if (mounted) {
        setState(() {
          ocupado = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final actual = pedido;
    return Scaffold(
      appBar: AppBar(
        title: Text(actual == null ? 'Pedido' : 'Pedido #${actual.numero}'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (ocupado) const LinearProgressIndicator(),
          if (aviso != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text(aviso!),
            ),
          if (noAccesible)
            OutlinedButton(
              onPressed: () => context.go('/pedidos'),
              child: const Text('Volver a pedidos'),
            ),
          if (actual == null && !noAccesible && !ocupado)
            OutlinedButton(onPressed: cargar, child: const Text('Reintentar')),
          if (actual != null && !noAccesible) ...[
            Text('Cliente: ${actual.cliente} · ${actual.estado}'),
            if (actual.cotizacion != null)
              ResumenCotizacionCard(
                cotizacion: actual.cotizacion!,
                aceptado: actual.aceptado,
              ),
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
                          (actual.renglones[i].resolucion == 'pendiente' ||
                              (errores['renglones_pendientes'] is List &&
                                  (errores['renglones_pendientes'] as List)
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
            if (!congelado) ...[
              FilledButton(
                onPressed: ocupado ? null : () => operar(publicar: false),
                child: const Text('Guardar renglones'),
              ),
              OutlinedButton(
                onPressed: ocupado ? null : () => operar(publicar: true),
                child: const Text('Publicar cotización'),
              ),
            ],
          ],
        ],
      ),
    );
  }
}
