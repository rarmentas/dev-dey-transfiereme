import 'dart:async';

class AsistenteLiveEvento {
  const AsistenteLiveEvento(this.tipo, [this.texto]);
  final String tipo;
  final String? texto;
}

class AsistenteLiveBridge {
  final StreamController<AsistenteLiveEvento> _eventos =
      StreamController.broadcast();
  Stream<AsistenteLiveEvento> get eventos => _eventos.stream;
  Future<void> iniciar(String token, String modelo) async => _eventos.add(
    const AsistenteLiveEvento(
      'error',
      'La voz en vivo está disponible en la versión web.',
    ),
  );
  void colgar() => _eventos.add(const AsistenteLiveEvento('cerrada'));
  void dispose() => _eventos.close();
}
