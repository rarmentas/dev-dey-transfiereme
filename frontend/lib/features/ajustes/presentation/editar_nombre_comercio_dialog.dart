import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/sesion/sesion_notifier.dart';
import '../../../core/ui/ui.dart';
import '../data/comercio_repository.dart';
import 'ajustes_providers.dart';

const _largoMaximoNombre = 200;

Future<void> mostrarEditarNombreComercio({
  required BuildContext context,
  required WidgetRef ref,
  required String nombreActual,
  ComercioRepository? repositorio,
}) {
  return showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (dialogContext) {
      return _EditarNombreComercioDialog(
        nombreInicial: nombreActual,
        repositorio: repositorio,
      );
    },
  );
}

class _EditarNombreComercioDialog extends ConsumerStatefulWidget {
  const _EditarNombreComercioDialog({
    required this.nombreInicial,
    this.repositorio,
  });

  final String nombreInicial;
  final ComercioRepository? repositorio;

  @override
  ConsumerState<_EditarNombreComercioDialog> createState() =>
      _EditarNombreComercioDialogState();
}

class _EditarNombreComercioDialogState
    extends ConsumerState<_EditarNombreComercioDialog> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _controller;

  var _guardando = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.nombreInicial);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  ComercioRepository get _repositorio =>
      widget.repositorio ?? ref.read(comercioRepositoryProvider);

  Future<void> _guardar() async {
    if (!_formKey.currentState!.validate() || _guardando) {
      return;
    }
    setState(() {
      _guardando = true;
      _error = null;
    });
    try {
      final resultado = await _repositorio.actualizarNombre(_controller.text);
      ref
          .read(sesionNotifierProvider.notifier)
          .actualizarNombreComercio(resultado.nombre);
      if (!mounted) {
        return;
      }
      Navigator.of(context).pop();
    } on ComercioApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() => _error = error.mensaje);
    } finally {
      if (mounted) {
        setState(() => _guardando = false);
      }
    }
  }

  String? _validarNombre(String? valor) {
    final texto = (valor ?? '').trim();
    if (texto.isEmpty) {
      return 'Indique el nombre del comercio.';
    }
    if (texto.length > _largoMaximoNombre) {
      return 'El nombre del comercio no puede pasar de 200 caracteres.';
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);

    return PopScope(
      canPop: !_guardando,
      child: AlertDialog(
      title: const Text('Nombre del comercio'),
      content: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextFormField(
              key: const Key('campo_nombre_comercio'),
              controller: _controller,
              maxLength: _largoMaximoNombre,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(
                labelText: 'Nombre',
                helperText: 'Así verán tu negocio en la app.',
              ),
              validator: _validarNombre,
              enabled: !_guardando,
            ),
            if (_error != null) ...[
              const SizedBox(height: TfSpace.s3),
              TfAvisoError(titulo: _error!),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          key: const Key('boton_cancelar_nombre_comercio'),
          onPressed: _guardando ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancelar'),
        ),
        FilledButton(
          key: const Key('boton_guardar_nombre_comercio'),
          onPressed: _guardando ? null : _guardar,
          child: _guardando
              ? const SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Guardar'),
        ),
      ],
      actionsPadding: const EdgeInsets.fromLTRB(
        TfSpace.s4,
        0,
        TfSpace.s4,
        TfSpace.s4,
      ),
      contentPadding: const EdgeInsets.fromLTRB(
        TfSpace.s5,
        TfSpace.s4,
        TfSpace.s5,
        TfSpace.s2,
      ),
      titleTextStyle: tema.textTheme.titleLarge,
      ),
    );
  }
}
