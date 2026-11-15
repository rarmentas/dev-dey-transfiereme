import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/cuenta_cobro.dart';
import '../data/cuentas_repository.dart';
import 'cuentas_providers.dart';
import 'widgets/cuenta_card.dart';

class CuentasPage extends ConsumerStatefulWidget {
  const CuentasPage({super.key});
  @override
  ConsumerState<CuentasPage> createState() => _CuentasPageState();
}

class _CuentasPageState extends ConsumerState<CuentasPage> {
  final clabe = TextEditingController();
  List<CuentaCobro>? cuentas;
  String? aviso;
  String? errorClabe;
  bool ocupado = false, bloqueado = false;
  final Map<String, Timer> espera = {};
  final Set<String> registroIncierto = {};
  @override
  void initState() {
    super.initState();
    cargar();
  }

  @override
  void dispose() {
    for (final timer in espera.values) {
      timer.cancel();
    }
    clabe.dispose();
    super.dispose();
  }

  Future<void> cargar({bool conservarAviso = false}) async {
    try {
      final lista = await ref.read(cuentasRepositoryProvider).listar();
      if (mounted) {
        setState(() {
          cuentas = lista;
          bloqueado = false;
          if (!conservarAviso) aviso = null;
        });
      }
    } on CuentasException catch (e) {
      if (mounted) {
        setState(() {
          aviso = e.mensaje;
          bloqueado = e.status == 401 || e.status == 403;
        });
      }
    }
  }

  Future<void> ejecutar(
    Future<void> Function() accion, {
    String? id,
    bool esRegistro = false,
  }) async {
    if (ocupado) return;
    setState(() {
      ocupado = true;
      aviso = null;
      errorClabe = null;
    });
    try {
      await accion();
      await cargar();
    } on CuentasException catch (e) {
      if (!mounted) return;
      setState(() {
        aviso = e.mensaje;
        if (e.codigo == 'CLABE_INVALIDA') errorClabe = e.mensaje;
        if (e.status == 401 || e.status == 403) bloqueado = true;
        if (id != null && e.codigo == 'SYNC_PRONTO') {
          espera.remove(id)?.cancel();
          espera[id] = Timer(Duration(seconds: e.reintento), () {
            if (mounted) setState(() => espera.remove(id));
          });
        }
        if (id != null &&
            esRegistro &&
            (e.status == null ||
                (e.status! >= 500 &&
                    e.codigo != 'PEY_RECHAZO' &&
                    e.codigo != 'ADAPTADOR_NO_PRODUCCION') ||
                e.codigo == 'REGISTRO_INCIERTO')) {
          registroIncierto.add(id);
        }
      });
      if (e.status == 404 ||
          e.codigo == 'VERSION_OBSOLETA' ||
          e.codigo == 'CUENTA_NO_ELEGIBLE' ||
          e.codigo == 'REGISTRO_INCIERTO' ||
          e.codigo == 'PEY_INCIERTO' ||
          (esRegistro && (e.status == null || e.status! >= 500))) {
        await cargar(conservarAviso: true);
      }
    } finally {
      if (mounted) setState(() => ocupado = false);
    }
  }

  Future<void> registrar(CuentaCobro cuenta) async {
    var nombre = '';
    var alias = '';
    String entidad = 'PERSON';
    final resultado = await showDialog<List<String>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, cambiar) => AlertDialog(
          title: const Text('Registrar cuenta'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                onChanged: (valor) => nombre = valor,
                decoration: const InputDecoration(labelText: 'Nombre'),
              ),
              TextField(
                onChanged: (valor) => alias = valor,
                decoration: const InputDecoration(labelText: 'Alias opcional'),
              ),
              DropdownButton<String>(
                value: entidad,
                items: const [
                  DropdownMenuItem(value: 'PERSON', child: Text('Persona')),
                  DropdownMenuItem(value: 'BUSINESS', child: Text('Negocio')),
                ],
                onChanged: (v) => cambiar(() => entidad = v!),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancelar'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(context, [
                nombre.trim(),
                entidad,
                alias.trim(),
              ]),
              child: const Text('Registrar'),
            ),
          ],
        ),
      ),
    );
    if (resultado != null && resultado[0].isNotEmpty) {
      await ejecutar(
        () async {
          await ref
              .read(cuentasRepositoryProvider)
              .registrar(
                cuenta.id,
                resultado[0],
                resultado[1],
                resultado[2],
                cuenta.version,
              );
        },
        id: cuenta.id,
        esRegistro: true,
      );
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Cuentas')),
    body: ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (aviso != null) Text(aviso!),
        if (!bloqueado) ...[
          if (cuentas == null && aviso != null)
            OutlinedButton(onPressed: cargar, child: const Text('Reintentar')),
          if (cuentas?.isEmpty == true) const Text('Aún no tienes cuentas'),
          for (final cuenta in cuentas ?? <CuentaCobro>[])
            CuentaCard(
              cuenta: cuenta,
              registroIncierto: registroIncierto.contains(cuenta.id),
              ocupado: ocupado || espera.containsKey(cuenta.id),
              registrar: () => registrar(cuenta),
              sincronizar: () => ejecutar(() async {
                await ref
                    .read(cuentasRepositoryProvider)
                    .sincronizar(cuenta.id);
              }, id: cuenta.id),
              elegir: () => ejecutar(() async {
                await ref
                    .read(cuentasRepositoryProvider)
                    .elegirPredeterminada(cuenta.id, cuenta.version);
              }, id: cuenta.id),
            ),
          TextField(
            controller: clabe,
            enabled: !ocupado,
            keyboardType: TextInputType.number,
            obscureText: true,
            decoration: InputDecoration(
              labelText: 'CLABE',
              errorText: errorClabe,
            ),
          ),
          FilledButton(
            onPressed: ocupado
                ? null
                : () {
                    if (!_clabeValida(clabe.text)) {
                      setState(
                        () => errorClabe =
                            'La CLABE debe tener 18 dígitos y ser válida.',
                      );
                      return;
                    }
                    ejecutar(() async {
                      await ref
                          .read(cuentasRepositoryProvider)
                          .crear(clabe.text);
                      clabe.clear();
                    });
                  },
            child: const Text('Agregar cuenta'),
          ),
        ],
      ],
    ),
  );
}

bool _clabeValida(String valor) {
  if (!RegExp(r'^\d{18}$').hasMatch(valor)) return false;
  const pesos = [3, 7, 1];
  var suma = 0;
  for (var i = 0; i < 17; i++) {
    suma += (int.parse(valor[i]) * pesos[i % 3]) % 10;
  }
  return (10 - suma % 10) % 10 == int.parse(valor[17]);
}
