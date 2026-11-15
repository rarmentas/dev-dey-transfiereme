import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/pedido.dart';
import 'pedido_providers.dart';
import 'widgets/renglon_editor.dart';

class CatalogoPage extends ConsumerStatefulWidget {
  const CatalogoPage({super.key});
  @override
  ConsumerState<CatalogoPage> createState() => _CatalogoPageState();
}

class _CatalogoPageState extends ConsumerState<CatalogoPage> {
  List<Map<String, dynamic>> productos = [];
  bool habilitado = false;
  bool esDueno = false;
  bool ocupado = false;
  String? error;

  @override
  void initState() {
    super.initState();
    cargar();
  }

  Future<void> cargar() async {
    setState(() => ocupado = true);
    try {
      final datos = await ref.read(pedidoRepositoryProvider).catalogo();
      if (!mounted) return;
      setState(() {
        productos = (datos['productos'] as List)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        habilitado = datos['agente_habilitado'] as bool;
        esDueno = datos['es_dueno'] as bool;
        error = null;
      });
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => ocupado = false);
    }
  }

  Future<void> editar([Map<String, dynamic>? anterior]) async {
    final nombre = TextEditingController(
      text: anterior?['nombre'] as String? ?? '',
    );
    final alias = TextEditingController(
      text: ((anterior?['alias'] as List?) ?? []).join(', '),
    );
    final unidad = TextEditingController(
      text: anterior?['unidad'] as String? ?? 'pieza',
    );
    final precio = TextEditingController(
      text: anterior?['precio_centavos'] == null
          ? ''
          : '${(anterior!['precio_centavos'] as int) ~/ 100}.${((anterior['precio_centavos'] as int) % 100).toString().padLeft(2, '0')}',
    );
    var disponible = anterior?['disponible'] as bool? ?? true;
    final guardar = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, cambiar) => AlertDialog(
          title: Text(anterior == null ? 'Nuevo producto' : 'Editar producto'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nombre,
                  decoration: const InputDecoration(labelText: 'Nombre'),
                ),
                TextField(
                  controller: alias,
                  decoration: const InputDecoration(
                    labelText: 'Alias separados por coma',
                  ),
                ),
                TextField(
                  controller: unidad,
                  decoration: const InputDecoration(
                    labelText: 'Unidad (kg, pieza, litro)',
                  ),
                ),
                TextField(
                  controller: precio,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: const InputDecoration(
                    labelText: 'Precio unitario en pesos; vacío = pendiente',
                  ),
                ),
                SwitchListTile(
                  value: disponible,
                  title: const Text('Disponible'),
                  onChanged: (v) => cambiar(() => disponible = v),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Guardar'),
            ),
          ],
        ),
      ),
    );
    if (guardar != true || !mounted) return;
    final centavos = precio.text.trim().isEmpty
        ? null
        : precioCentavos(precio.text);
    if (nombre.text.trim().isEmpty ||
        unidad.text.trim().isEmpty ||
        (precio.text.trim().isNotEmpty && centavos == null)) {
      setState(() => error = 'Revisa nombre, unidad y precio.');
      return;
    }
    setState(() => ocupado = true);
    try {
      await ref.read(pedidoRepositoryProvider).guardarProducto(
        anterior?['id'] as int?,
        {
          'nombre': nombre.text.trim(),
          'alias': alias.text
              .split(',')
              .map((e) => e.trim())
              .where((e) => e.isNotEmpty)
              .toList(),
          'unidad': unidad.text.trim(),
          'precio_centavos': centavos,
          'disponible': disponible,
        },
      );
      await cargar();
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => ocupado = false);
    }
  }

  Future<void> activar(bool valor) async {
    setState(() => ocupado = true);
    try {
      await ref.read(pedidoRepositoryProvider).configurarAgente(valor);
      if (mounted) {
        setState(() {
          habilitado = valor;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => ocupado = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Lista de precios'),
      actions: [
        IconButton(
          onPressed: ocupado ? null : cargar,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    floatingActionButton: FloatingActionButton(
      onPressed: ocupado ? null : () => editar(),
      child: const Icon(Icons.add),
    ),
    body: ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (ocupado) const LinearProgressIndicator(),
        if (error != null) Text(error!),
        if (esDueno)
          SwitchListTile(
            title: const Text('Agente de pedidos'),
            subtitle: const Text(
              'Atienden pedidos por WhatsApp con esta lista de precios.',
            ),
            value: habilitado,
            onChanged: ocupado ? null : activar,
          ),
        for (final p in productos)
          Card(
            child: ListTile(
              title: Text(p['nombre'] as String),
              subtitle: Text(
                '${p['unidad']} · ${p['precio_centavos'] == null ? 'Sin precio autorizado' : formatearCentavos(p['precio_centavos'] as int)}${p['disponible'] == true ? '' : ' · No disponible'}',
              ),
              trailing: const Icon(Icons.edit),
              onTap: ocupado ? null : () => editar(p),
            ),
          ),
      ],
    ),
  );
}
