import 'dart:convert';
import 'dart:math';

String nuevaClaveComando() {
  final random = Random.secure();
  return List.generate(
    32,
    (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0'),
  ).join();
}

class ClaveComando {
  String? _huella;
  String? _clave;
  String para(Object payload) {
    final huella = jsonEncode(payload);
    if (_huella != huella) {
      _huella = huella;
      _clave = nuevaClaveComando();
    }
    return _clave!;
  }

  void limpiar() {
    _huella = null;
    _clave = null;
  }
}
