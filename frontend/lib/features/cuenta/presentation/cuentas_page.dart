import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/ui/ui.dart';
import '../../../theme/transfiereme_theme.dart';
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
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextField(
                  onChanged: (valor) => nombre = valor,
                  decoration: const InputDecoration(labelText: 'Nombre'),
                ),
                const SizedBox(height: TfSpace.s3),
                TextField(
                  onChanged: (valor) => alias = valor,
                  decoration: const InputDecoration(
                    labelText: 'Alias opcional',
                  ),
                ),
                const SizedBox(height: TfSpace.s3),
                DropdownButtonFormField<String>(
                  initialValue: entidad,
                  decoration: const InputDecoration(
                    labelText: 'Tipo de cuenta',
                  ),
                  items: const [
                    DropdownMenuItem(value: 'PERSON', child: Text('Persona')),
                    DropdownMenuItem(value: 'BUSINESS', child: Text('Negocio')),
                  ],
                  onChanged: (v) => cambiar(() => entidad = v!),
                ),
              ],
            ),
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
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final mostrandoCarga = cuentas == null && aviso == null;

    return Scaffold(
      appBar: AppBar(title: const Text('Cuentas')),
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
                Text(
                  'Tu cuenta para cobrar',
                  style: tema.textTheme.headlineLarge,
                ),
                const SizedBox(height: TfSpace.s1),
                Text(
                  'Registra y elige la cuenta donde recibirás tus pagos.',
                  style: tema.textTheme.bodyMedium?.copyWith(
                    color: tema.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: TfSpace.s3),
                if (mostrandoCarga)
                  const _CuentasCargando()
                else if (aviso != null)
                  _AvisoCuentas(
                    mensaje: aviso!,
                    reintentar: !bloqueado ? cargar : null,
                  ),
                if (!bloqueado && cuentas?.isEmpty == true) ...[
                  const _CuentasVacias(),
                  const SizedBox(height: TfSpace.s2),
                ],
                if (!bloqueado) ...[
                  for (final cuenta in cuentas ?? <CuentaCobro>[]) ...[
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
                    const SizedBox(height: TfSpace.s3),
                  ],
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(TfSpace.s4),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text(
                            'Agregar una cuenta',
                            style: tema.textTheme.headlineSmall,
                          ),
                          const SizedBox(height: TfSpace.s1),
                          Text(
                            'Ingresa los 18 dígitos de tu CLABE.',
                            style: tema.textTheme.bodySmall,
                          ),
                          const SizedBox(height: TfSpace.s4),
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
                          const SizedBox(height: TfSpace.s3),
                          FilledButton.icon(
                            onPressed: ocupado ? null : _agregarCuenta,
                            icon: ocupado
                                ? const SizedBox(
                                    width: 20,
                                    height: 20,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                    ),
                                  )
                                : const Icon(Icons.add_rounded),
                            label: Text(
                              ocupado ? 'Guardando cuenta…' : 'Agregar cuenta',
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _agregarCuenta() {
    if (!_clabeValida(clabe.text)) {
      setState(
        () => errorClabe = 'La CLABE debe tener 18 dígitos y ser válida.',
      );
      return;
    }
    ejecutar(() async {
      await ref.read(cuentasRepositoryProvider).crear(clabe.text);
      clabe.clear();
    });
  }
}

class _CuentasCargando extends StatelessWidget {
  const _CuentasCargando();

  @override
  Widget build(BuildContext context) {
    final color =
        Theme.of(context).extension<TfColors>()?.pending ??
        Theme.of(context).colorScheme.primary;
    return Semantics(
      label: 'Cargando cuentas',
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(TfSpace.s4),
          child: Row(
            children: [
              Icon(Icons.hourglass_top_rounded, color: color, size: 24),
              const SizedBox(width: TfSpace.s3),
              const Expanded(child: Text('Cargando tus cuentas…')),
            ],
          ),
        ),
      ),
    );
  }
}

class _AvisoCuentas extends StatelessWidget {
  const _AvisoCuentas({required this.mensaje, this.reintentar});
  final String mensaje;
  final VoidCallback? reintentar;

  @override
  Widget build(BuildContext context) => Card(
    color: Theme.of(context).colorScheme.errorContainer,
    child: Padding(
      padding: const EdgeInsets.all(TfSpace.s3),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('No pudimos cargar tus cuentas', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: TfSpace.s1),
          Text(mensaje),
          if (reintentar != null)
            TextButton.icon(
              onPressed: reintentar,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Reintentar'),
            ),
        ],
      ),
    ),
  );
}

class _CuentasVacias extends StatelessWidget {
  const _CuentasVacias();
  @override
  Widget build(BuildContext context) => Card(
    child: const Padding(
      padding: EdgeInsets.all(TfSpace.s3),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Aún no tienes cuentas'),
          SizedBox(height: TfSpace.s1),
          Text('Agrega tu CLABE para comenzar a recibir cobros.'),
        ],
      ),
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
