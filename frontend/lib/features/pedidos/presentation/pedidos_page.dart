import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../data/pedido.dart';
import 'pedido_providers.dart';

class PedidosPage extends ConsumerStatefulWidget {
  const PedidosPage({super.key});
  @override
  ConsumerState<PedidosPage> createState() => _PedidosPageState();
}

class _PedidosPageState extends ConsumerState<PedidosPage> {
  List<PedidoResumen>? pedidos;
  String? error;
  bool cargando = false;
  @override
  void initState() {
    super.initState();
    cargar();
  }

  Future<void> cargar() async {
    if (cargando) return;
    setState(() {
      cargando = true;
    });
    try {
      final lista = await ref.read(pedidoRepositoryProvider).listar();
      if (mounted) {
        setState(() {
          pedidos = lista;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          error = e.toString();
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          cargando = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Pedidos'),
      actions: [
        IconButton(
          onPressed: cargando ? null : cargar,
          icon: const Icon(Icons.refresh),
          tooltip: 'Actualizar',
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (cargando && pedidos == null)
          const Center(child: CircularProgressIndicator()),
        if (error != null) Text(error!),
        if (pedidos != null && pedidos!.isEmpty) ...[
          const Text(
            'Aún no hay pedidos. Cuando un cliente pida por WhatsApp aparecerá aquí.',
          ),
          OutlinedButton(
            onPressed: cargando ? null : cargar,
            child: const Text('Actualizar'),
          ),
        ],
        for (final pedido in pedidos ?? <PedidoResumen>[])
          Card(
            child: ListTile(
              title: Text('Pedido #${pedido.numero} · ${pedido.cliente}'),
              subtitle: Text(
                '${pedido.estado} · Pago: ${etiquetaPago(pedido.pagoEstado)} · Preparación: ${etiquetaPreparacion(pedido.preparacion)} · ${pedido.pendientes} pendientes${pedido.total == null ? '' : ' · ${formatearCentavos(pedido.total!)}'}',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () async {
                await context.push('/pedidos/${pedido.id}');
                if (mounted) cargar();
              },
            ),
          ),
      ],
    ),
  );
}
