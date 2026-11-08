import 'package:cody/core/sesion/sesion_repository.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/mock_sesion_api.dart';

void main() {
  test('entrar y estado con mock', () async {
    final dio = crearDioPrueba();
    prepararDioConSesion(dio);
    final repo = SesionRepository(dio);
    await repo.entrar(correo: 'lupe@tortilleria.mx', contrasena: 'clave');
    final estado = await repo.cargarEstado();
    expect(estado?.nombre, 'Lupe');
  });

  test('entrar tras arranque sin sesión', () async {
    final dio = crearDioPrueba();
    prepararDioConSesion(dio);
    final repo = SesionRepository(dio);
    expect(await repo.cargarEstado(), isNull);
    await repo.entrar(correo: 'lupe@tortilleria.mx', contrasena: 'clave');
    expect((await repo.cargarEstado())?.nombre, 'Lupe');
  });
}
