import 'package:cody/features/venta/data/venta_repository.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/mock_venta_api.dart';

void main() {
  test('crearNotificacion devuelve la venta con telefono_final', () async {
    final mock = MockVentaApi(crearDioVenta());
    mock.alCrearNotificacion(201, cuerpoNotificacion(id: 3));
    final venta = await VentaRepository(mock.dio).crearNotificacion(
      monto: '120',
      telefono: '5512344321',
    );
    expect(venta.movimientoId, 3);
    expect(venta.esNotificacion, isTrue);
    expect(venta.telefonoFinal, '4321');
    expect(mock.peticiones.single.path, rutaCrearNotificacion);
  });

  test('crearNotificacion 409 con movimiento es venta pendiente', () async {
    final mock = MockVentaApi(crearDioVenta());
    mock.alCrearNotificacion(409, {'detail': 'x', 'movimiento_id': 9});
    expect(
      VentaRepository(mock.dio)
          .crearNotificacion(monto: '1', telefono: '5512344321'),
      throwsA(isA<VentaPendienteException>()),
    );
  });

  test('crearNotificacion 409 sin movimiento es cuenta no activa', () async {
    final mock = MockVentaApi(crearDioVenta());
    mock.alCrearNotificacion(409, {'detail': 'La cuenta no está ACTIVE.'});
    expect(
      VentaRepository(mock.dio)
          .crearNotificacion(monto: '1', telefono: '5512344321'),
      throwsA(isA<CuentaNoActiveException>()),
    );
  });

  test('crearNotificacion 400 es validación', () async {
    final mock = MockVentaApi(crearDioVenta());
    mock.alCrearNotificacion(400, {
      'telefono': ['El teléfono debe ser de 10 dígitos.'],
    });
    expect(
      VentaRepository(mock.dio)
          .crearNotificacion(monto: '1', telefono: '123'),
      throwsA(isA<ValidacionVentaException>()),
    );
  });

  test('crearNotificacion 502 es Pey', () async {
    final mock = MockVentaApi(crearDioVenta());
    mock.alCrearNotificacion(502, {
      'detail': 'Puede que la notificación haya llegado.',
      'puede_haberse_creado': true,
    });
    expect(
      VentaRepository(mock.dio)
          .crearNotificacion(monto: '1', telefono: '5512344321'),
      throwsA(
        isA<PeyException>().having((e) => e.puedeHaberseCreado, 'p', true),
      ),
    );
  });
}
