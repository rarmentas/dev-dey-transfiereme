import 'package:flutter_test/flutter_test.dart';
import 'package:cody/features/pedidos/data/clave_comando.dart';
import 'package:cody/features/pedidos/presentation/widgets/renglon_editor.dart';

void main() {
  test('misma clave para mismo payload y nueva al cambiar', () {
    final clave = ClaveComando();
    final primera = clave.para({'cantidad': '1'});
    expect(primera, matches(RegExp(r'^[0-9a-f]{64}$')));
    expect(clave.para({'cantidad': '1'}), primera);
    expect(clave.para({'cantidad': '2'}), isNot(primera));
  });
  test('precio acepta centavos exactos y rechaza valores inválidos', () {
    expect(precioCentavos('12.5'), 1250);
    for (final valor in ['0', '-1', '1.001', '1e2', '', 'NaN']) {
      expect(precioCentavos(valor), isNull);
    }
  });
}
