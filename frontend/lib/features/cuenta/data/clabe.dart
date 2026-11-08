const mensajeClabeInvalida = 'Escribe una CLABE válida de 18 dígitos.';

const _pesos = [3, 7, 1];

/// Misma regla que el servidor: 18 dígitos y dígito verificador Banxico.
String? validarClabe(String valor) {
  final clabe = valor.trim();
  if (clabe.length != 18 || int.tryParse(clabe) == null) {
    return mensajeClabeInvalida;
  }
  var total = 0;
  for (var i = 0; i < 17; i++) {
    total += int.parse(clabe[i]) * _pesos[i % 3];
  }
  final esperado = (10 - (total % 10)) % 10;
  if (esperado != int.parse(clabe[17])) {
    return mensajeClabeInvalida;
  }
  return null;
}
