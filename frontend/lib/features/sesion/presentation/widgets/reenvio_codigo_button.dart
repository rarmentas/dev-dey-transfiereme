import 'dart:async';

import 'package:flutter/material.dart';

typedef ReenviarCodigoCallback = Future<bool> Function();

class ReenvioCodigoButton extends StatefulWidget {
  const ReenvioCodigoButton({
    super.key,
    required this.onReenviar,
    this.cooldown = const Duration(seconds: 60),
    this.habilitado = true,
    this.iniciarEnEspera = false,
  });

  final ReenviarCodigoCallback onReenviar;
  final Duration cooldown;
  final bool habilitado;
  /// Si es verdadero, arranca la cuenta regresiva al montar (p. ej. tras el primer envío).
  final bool iniciarEnEspera;

  @override
  State<ReenvioCodigoButton> createState() => _ReenvioCodigoButtonState();
}

class _ReenvioCodigoButtonState extends State<ReenvioCodigoButton> {
  Timer? _timer;
  int _segundosRestantes = 0;
  bool _reenviando = false;

  bool get _enEspera => _segundosRestantes > 0;

  @override
  void initState() {
    super.initState();
    if (widget.iniciarEnEspera) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _iniciarEspera();
        }
      });
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _iniciarEspera() {
    _timer?.cancel();
    setState(() => _segundosRestantes = widget.cooldown.inSeconds);
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      if (_segundosRestantes <= 1) {
        timer.cancel();
        setState(() => _segundosRestantes = 0);
      } else {
        setState(() => _segundosRestantes -= 1);
      }
    });
  }

  Future<void> _pulsar() async {
    if (_enEspera || _reenviando || !widget.habilitado) {
      return;
    }
    setState(() => _reenviando = true);
    try {
      final enviado = await widget.onReenviar();
      if (enviado && mounted) {
        _iniciarEspera();
      }
    } finally {
      if (mounted) {
        setState(() => _reenviando = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final puedePulsar =
        widget.habilitado && !_enEspera && !_reenviando;
    final etiqueta = _enEspera
        ? 'Enviar otro código ($_segundosRestantes s)'
        : 'Enviar otro código';

    return TextButton(
      key: const Key('boton_reenviar_codigo'),
      onPressed: puedePulsar ? _pulsar : null,
      child: _reenviando
          ? const SizedBox(
              height: 20,
              width: 20,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : Text(etiqueta),
    );
  }
}
