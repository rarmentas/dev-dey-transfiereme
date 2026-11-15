import 'package:cody/core/ui/tf_tokens.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../data/pedido.dart';
import 'pedido_providers.dart';
import 'widgets/pedido_estado_chip.dart';

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
    setState(() => cargando = true);
    try {
      final lista = await ref.read(pedidoRepositoryProvider).listar();
      if (mounted) {
        setState(() {
          pedidos = lista;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => cargando = false);
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
    body: SafeArea(
      top: false,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: kMaxAnchoContenido),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(
              kMargenPantalla,
              TfSpace.s4,
              kMargenPantalla,
              TfSpace.s6,
            ),
            children: [
              if (cargando && pedidos == null) const _CargaPedidos(),
              if (cargando && pedidos != null) ...[
                Semantics(
                  label: 'Actualizando pedidos',
                  child: LinearProgressIndicator(
                    color: Theme.of(context).colorScheme.secondary,
                  ),
                ),
                const SizedBox(height: TfSpace.s3),
              ],
              if (error != null)
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('No pudimos cargar los pedidos'),
                    Text(error!),
                    OutlinedButton(
                      onPressed: cargando ? null : cargar,
                      child: const Text('Reintentar'),
                    ),
                  ],
                ),
              if (pedidos != null && pedidos!.isEmpty)
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Aún no hay pedidos. Cuando un cliente pida por WhatsApp aparecerá aquí.',
                    ),
                    OutlinedButton(
                      onPressed: cargando ? null : cargar,
                      child: const Text('Actualizar'),
                    ),
                  ],
                ),
              for (final pedido in pedidos ?? <PedidoResumen>[])
                _PedidoTile(
                  pedido: pedido,
                  alAbrir: () async {
                    await context.push('/pedidos/${pedido.id}');
                    if (mounted) {
                      cargar();
                    }
                  },
                ),
            ],
          ),
        ),
      ),
    ),
  );
}

class _PedidoTile extends StatelessWidget {
  const _PedidoTile({required this.pedido, required this.alAbrir});
  final PedidoResumen pedido;
  final VoidCallback alAbrir;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: TfSpace.s3),
    child: Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(TfRadius.lg),
        onTap: alAbrir,
        child: Padding(
          padding: const EdgeInsets.all(TfSpace.s4),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Pedido #${pedido.numero}',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: TfSpace.s1),
                    Text(
                      pedido.cliente,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: TfSpace.s3),
                    Wrap(
                      spacing: TfSpace.s2,
                      runSpacing: TfSpace.s2,
                      children: [
                        PedidoEstadoChip.comercial(estado: pedido.estado),
                        PedidoEstadoChip.pago(estado: pedido.pagoEstado),
                        PedidoEstadoChip.preparacion(
                          estado: pedido.preparacion,
                        ),
                        if (pedido.pendientes > 0)
                          PedidoEstadoChip.comercial(estado: 'borrador'),
                      ],
                    ),
                    const SizedBox(height: TfSpace.s3),
                    Text(
                      pedido.total == null
                          ? 'Por cotizar'
                          : formatearCentavos(pedido.total!),
                      style: Theme.of(context).textTheme.titleMedium
                          ?.copyWith(),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: TfSpace.s2),
              const Padding(
                padding: EdgeInsets.only(top: TfSpace.s2),
                child: Icon(Icons.chevron_right_rounded),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

class _CargaPedidos extends StatelessWidget {
  const _CargaPedidos();
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: TfSpace.s12),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(
              color: Theme.of(context).colorScheme.secondary,
            ),
            const SizedBox(height: TfSpace.s3),
            Text(
              'Cargando pedidos…',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }
}
