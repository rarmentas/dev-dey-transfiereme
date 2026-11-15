import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../../../core/ui/ui.dart';
import '../data/asistente_live_bridge.dart';
import '../data/asistente_vivo_repository.dart';

final asistenteVivoRepositoryProvider = Provider<AsistenteVivoRepository>(
  (ref) => AsistenteVivoRepository(ref.watch(dioProvider)),
);

enum EstadoAsistente {
  listo,
  conectando,
  escuchando,
  hablando,
  error,
  terminado,
}

class AsistenteVivoPage extends ConsumerStatefulWidget {
  const AsistenteVivoPage({super.key});
  @override
  ConsumerState<AsistenteVivoPage> createState() => _AsistenteVivoPageState();
}

class _AsistenteVivoPageState extends ConsumerState<AsistenteVivoPage> {
  final _bridge = AsistenteLiveBridge();
  StreamSubscription<AsistenteLiveEvento>? _sub;
  EstadoAsistente _estado = EstadoAsistente.listo;
  String _mensaje =
      'Toca iniciar y permite el micrófono para hablar con tu asistente.';
  String _tendero = '';
  String _asistente = '';

  @override
  void initState() {
    super.initState();
    _sub = _bridge.eventos.listen(_evento);
  }

  void _evento(AsistenteLiveEvento e) {
    if (!mounted) return;
    setState(() {
      switch (e.tipo) {
        case 'connected':
          _estado = EstadoAsistente.escuchando;
          _mensaje = 'Te escucho.';
        case 'listening':
          _estado = EstadoAsistente.escuchando;
        case 'speaking':
          _estado = EstadoAsistente.hablando;
        case 'inputTranscript':
          _tendero = e.texto ?? _tendero;
        case 'outputTranscript':
          _asistente = e.texto ?? _asistente;
        case 'error':
          _estado = EstadoAsistente.error;
          _mensaje = e.texto ?? 'Ocurrió un error al conectar.';
        case 'closed':
        case 'cerrada':
          _estado = EstadoAsistente.terminado;
          _mensaje = 'Sesión terminada.';
      }
    });
  }

  Future<void> _alternar() async {
    if (_estado == EstadoAsistente.escuchando ||
        _estado == EstadoAsistente.hablando ||
        _estado == EstadoAsistente.conectando) {
      _bridge.colgar();
      return;
    }
    setState(() {
      _estado = EstadoAsistente.conectando;
      _mensaje = 'Conectando de forma segura…';
      _tendero = '';
      _asistente = '';
    });
    try {
      final token = await ref
          .read(asistenteVivoRepositoryProvider)
          .pedirToken();
      await _bridge.iniciar(token.token, token.modelo);
    } on AsistenteVivoException catch (e) {
      if (mounted)
        setState(() {
          _estado = EstadoAsistente.error;
          _mensaje = e.mensaje;
        });
    }
  }

  @override
  void dispose() {
    _sub?.cancel();
    _bridge.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final activo =
        _estado == EstadoAsistente.escuchando ||
        _estado == EstadoAsistente.hablando ||
        _estado == EstadoAsistente.conectando;
    final etiqueta = switch (_estado) {
      EstadoAsistente.conectando => 'Conectando',
      EstadoAsistente.escuchando => 'Escuchando',
      EstadoAsistente.hablando => 'Hablando',
      EstadoAsistente.error => 'Error',
      EstadoAsistente.terminado => 'Sesión terminada',
      _ => 'Asistente en vivo',
    };
    return Scaffold(
      appBar: AppBar(title: const Text('Asistente en vivo')),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: kMaxAnchoContenido),
            child: ListView(
              padding: const EdgeInsets.all(kMargenPantalla),
              children: [
                Semantics(
                  liveRegion: true,
                  child: Text(etiqueta, style: tema.textTheme.headlineMedium),
                ),
                const SizedBox(height: TfSpace.s2),
                Text(
                  _mensaje,
                  style: tema.textTheme.bodyLarge?.copyWith(
                    color: tema.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: TfSpace.s6),
                Center(
                  child: FilledButton.icon(
                    key: const Key('boton_asistente_vivo'),
                    onPressed: _alternar,
                    icon: Icon(
                      activo ? Icons.call_end_rounded : Icons.mic_rounded,
                    ),
                    label: Text(activo ? 'Colgar' : 'Iniciar conversación'),
                    style: FilledButton.styleFrom(
                      minimumSize: const Size(220, 56),
                    ),
                  ),
                ),
                const SizedBox(height: TfSpace.s6),
                _Transcripcion(
                  titulo: 'Tú',
                  texto: _tendero,
                  icono: Icons.person_outline_rounded,
                ),
                const SizedBox(height: TfSpace.s3),
                _Transcripcion(
                  titulo: 'Asistente',
                  texto: _asistente,
                  icono: Icons.graphic_eq_rounded,
                ),
                const SizedBox(height: TfSpace.s5),
                Text(
                  'Puede consultar tus ventas y pedidos. Por seguridad, no realiza cambios ni cobros.',
                  style: tema.textTheme.bodySmall?.copyWith(
                    color: tema.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Transcripcion extends StatelessWidget {
  const _Transcripcion({
    required this.titulo,
    required this.texto,
    required this.icono,
  });
  final String titulo;
  final String texto;
  final IconData icono;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(TfSpace.s4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icono),
          const SizedBox(width: TfSpace.s3),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(titulo, style: Theme.of(context).textTheme.labelLarge),
                Text(texto.isEmpty ? 'Esperando…' : texto),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}
