import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/sesion/sesion_notifier.dart';
import '../../../core/ui/ui.dart';
import '../data/cuenta_estado.dart';
import '../data/cuenta_estado_repository.dart';
import 'cuenta_providers.dart';

class RegistrarCuentaPeyPage extends ConsumerStatefulWidget {
  const RegistrarCuentaPeyPage({super.key, this.repositorio});

  final CuentaEstadoRepository? repositorio;

  @override
  ConsumerState<RegistrarCuentaPeyPage> createState() =>
      _RegistrarCuentaPeyPageState();
}

class _RegistrarCuentaPeyPageState extends ConsumerState<RegistrarCuentaPeyPage> {
  final _formKey = GlobalKey<FormState>();
  final _nombreController = TextEditingController();
  final _aliasController = TextEditingController();

  var _entidad = 'PERSON';
  var _guardando = false;
  var _nombrePrellenado = false;
  String? _error;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_nombrePrellenado) {
      return;
    }
    _nombrePrellenado = true;
    final sesion = ref.read(sesionNotifierProvider).estado;
    if (sesion != null) {
      final partes = [sesion.nombre.trim(), sesion.apellidos.trim()]
          .where((p) => p.isNotEmpty)
          .join(' ');
      if (partes.isNotEmpty) {
        _nombreController.text = partes;
      }
    }
  }

  @override
  void dispose() {
    _nombreController.dispose();
    _aliasController.dispose();
    super.dispose();
  }

  CuentaEstadoRepository get _repositorio =>
      widget.repositorio ?? ref.read(cuentaEstadoRepositoryProvider);

  Future<bool> _confirmarReemplazo() async {
    final respuesta = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('¿Reemplazar la cuenta en pey?'),
        content: const Text(
          'Ya hay una cuenta registrada en pey para este comercio. '
          'Si continúas, se creará otra y el vínculo anterior quedará obsoleto.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            key: const Key('confirmar_reemplazo_pey'),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Sí, reemplazar'),
          ),
        ],
      ),
    );
    return respuesta == true;
  }

  Future<void> _enviar({required bool reemplazar}) async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    setState(() {
      _guardando = true;
      _error = null;
    });
    try {
      await _repositorio.registrarEnPey(
        nombre: _nombreController.text,
        entidad: _entidad,
        alias: _aliasController.text,
        reemplazar: reemplazar,
      );
      ref.invalidate(cuentaEstadoProvider);
      if (mounted) {
        context.pop();
      }
    } on CuentaPeyApiException catch (error) {
      if (error.codigo == 'CUENTA_PEY_YA_REGISTRADA') {
        final ok = await _confirmarReemplazo();
        if (ok && mounted) {
          await _enviar(reemplazar: true);
          return;
        }
      }
      if (error.codigo == 'PEY_INCIERTO' && mounted) {
        setState(() {
          _error =
              '${error.mensaje} Revisa el estado antes de volver a registrar.';
        });
        ref.invalidate(cuentaEstadoProvider);
        return;
      }
      setState(() => _error = error.mensaje);
    } catch (_) {
      setState(() => _error = 'No pudimos registrar la cuenta. Inténtalo de nuevo.');
    } finally {
      if (mounted) {
        setState(() => _guardando = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Registrar en pey')),
      body: SafeArea(
        child: Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: kMaxAnchoContenido),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(
                kMargenPantalla,
                TfSpace.s5,
                kMargenPantalla,
                TfSpace.s6,
              ),
              children: [
                Text(
                  'Paso 2: registro en pey',
                  style: tema.textTheme.titleLarge,
                ),
                const SizedBox(height: TfSpace.s2),
                Text(
                  'Usamos la CLABE que ya guardaste. Pey validará la cuenta para cobrar con CoDi.',
                  style: tema.textTheme.bodyMedium?.copyWith(
                    color: tema.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: TfSpace.s5),
                Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      TextFormField(
                        key: const Key('campo_nombre_titular'),
                        controller: _nombreController,
                        decoration: const InputDecoration(
                          labelText: 'Nombre del titular',
                        ),
                        textInputAction: TextInputAction.next,
                        validator: (valor) {
                          final texto = (valor ?? '').trim();
                          if (texto.isEmpty) {
                            return 'Indique el nombre del titular';
                          }
                          if (texto.length > 255) {
                            return 'Máximo 255 caracteres';
                          }
                          return null;
                        },
                      ),
                      const SizedBox(height: TfSpace.s4),
                      TextFormField(
                        controller: _aliasController,
                        decoration: const InputDecoration(
                          labelText: 'Alias (opcional)',
                          helperText: 'Si lo dejas vacío usamos el nombre.',
                        ),
                      ),
                      const SizedBox(height: TfSpace.s4),
                      Text(
                        'Tipo de titular',
                        style: tema.textTheme.titleSmall,
                      ),
                      const SizedBox(height: TfSpace.s2),
                      TfSegmentado<String>(
                        valor: _entidad,
                        opciones: const {
                          'PERSON': 'Persona',
                          'BUSINESS': 'Negocio',
                        },
                        onCambio: (valor) => setState(() => _entidad = valor),
                      ),
                      if (_error != null) ...[
                        const SizedBox(height: TfSpace.s4),
                        TfAvisoError(titulo: _error!),
                      ],
                    ],
                  ),
                ),
                const SizedBox(height: TfSpace.s6),
                FilledButton(
                  key: const Key('boton_enviar_registro_pey'),
                  onPressed: _guardando ? null : () => _enviar(reemplazar: false),
                  child: _guardando
                      ? const SizedBox(
                          height: 22,
                          width: 22,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Registrar en pey'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
