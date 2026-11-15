// ignore_for_file: deprecated_member_use, avoid_web_libraries_in_flutter

import 'dart:async';
import 'dart:convert';
import 'dart:html';
import 'dart:js_interop';

@JS('transfieremeLiveStart')
external void _iniciarJs(JSString token, JSString modelo);

@JS('transfieremeLiveStop')
external void _colgarJs();

class AsistenteLiveEvento {
  const AsistenteLiveEvento(this.tipo, [this.texto]);
  final String tipo;
  final String? texto;
}

/// Puente delgado a Web Audio/WebSocket. La llave nunca entra aquí: solo token.
class AsistenteLiveBridge {
  AsistenteLiveBridge() {
    _sub = window.onMessage.listen((event) {
      final data = event.data;
      // Los objetos JS no siempre se convierten a Map de Dart. El puente envía
      // JSON para que los eventos funcionen igual con los renderers web.
      if (data is String) {
        try {
          final decoded = jsonDecode(data);
          if (decoded is Map && decoded['source'] == 'transfiereme-live') {
            _eventos.add(
              AsistenteLiveEvento(
                '${decoded['type']}',
                decoded['text'] as String?,
              ),
            );
          }
        } on FormatException {
          // Mensaje ajeno a este puente.
        }
      }
    });
  }

  final StreamController<AsistenteLiveEvento> _eventos =
      StreamController.broadcast();
  late final StreamSubscription<MessageEvent> _sub;
  Stream<AsistenteLiveEvento> get eventos => _eventos.stream;

  Future<void> iniciar(String token, String modelo) async {
    _iniciarJs(token.toJS, modelo.toJS);
  }

  void colgar() => _colgarJs();

  void dispose() {
    colgar();
    _sub.cancel();
    _eventos.close();
  }
}
