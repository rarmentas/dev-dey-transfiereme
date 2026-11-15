import 'package:cody/features/venta/data/venta_repository.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/mock_venta_api.dart';

void main() {
  for (final notificacion in [false, true]) {
    test(
      'I8 cuenta inactiva 409 historico ${notificacion ? 'push' : 'QR'}',
      () async {
        final mock = MockVentaApi(crearDioVenta());
        final payload = {'detail': 'La cuenta no está ACTIVE.'};
        if (notificacion) {
          mock.alCrearNotificacion(409, payload);
        } else {
          mock.alCrear(409, payload);
        }
        final repo = VentaRepository(mock.dio);
        await expectLater(
          notificacion
              ? repo.crearNotificacion(monto: '1', telefono: '5512344321')
              : repo.crear(monto: '1'),
          throwsA(isA<CuentaNoActiveException>()),
        );
      },
    );
  }

  test('I8 codigo distinto tiene prioridad sobre texto historico', () async {
    final mock = MockVentaApi(crearDioVenta());
    mock.alCrear(409, {
      'codigo': 'COBRO_INCIERTO',
      'detail': 'La cuenta no está ACTIVE.',
    });
    await expectLater(
      VentaRepository(mock.dio).crear(monto: '1'),
      throwsA(
        isA<VentaApiException>().having(
          (e) => e.mensaje,
          'aviso',
          contains('no lo repitas'),
        ),
      ),
    );
  });
  test(
    'I8 sin codigo ni detalle historico no supone cuenta inactiva',
    () async {
      final mock = MockVentaApi(crearDioVenta());
      mock.alCrear(409, {'detail': 'Otro conflicto'});
      await expectLater(
        VentaRepository(mock.dio).crear(monto: '1'),
        throwsA(isA<VentaApiException>()),
      );
    },
  );

  test(
    'I8 movimiento pendiente prevalece sobre el detalle historico',
    () async {
      final mock = MockVentaApi(crearDioVenta());
      mock.alCrear(409, {
        'movimiento_id': 12,
        'detail': 'La cuenta no está ACTIVE.',
      });
      await expectLater(
        VentaRepository(mock.dio).crear(monto: '1'),
        throwsA(
          isA<VentaPendienteException>().having(
            (e) => e.movimientoId,
            'movimiento',
            12,
          ),
        ),
      );
    },
  );

  test('timeout conserva clave y payload distinto genera otra', () async {
    final mock = MockVentaApi(crearDioVenta());
    mock.alCrear(502, {'puede_haberse_creado': true});
    final repo = VentaRepository(mock.dio);
    for (final monto in ['10', '10', '11']) {
      await expectLater(repo.crear(monto: monto), throwsA(isA<PeyException>()));
    }
    final claves = mock.peticiones
        .map((p) => p.headers['Idempotency-Key'])
        .toList();
    expect(claves[0], isNotEmpty);
    expect(claves[1], claves[0]);
    expect(claves[2], isNot(claves[0]));
  });

  test('rechazo definitivo limpia la clave', () async {
    final mock = MockVentaApi(crearDioVenta());
    mock.alCrear(502, {'puede_haberse_creado': false});
    final repo = VentaRepository(mock.dio);
    for (var i = 0; i < 2; i++) {
      await expectLater(repo.crear(monto: '10'), throwsA(isA<PeyException>()));
    }
    expect(
      mock.peticiones[0].headers['Idempotency-Key'],
      isNot(mock.peticiones[1].headers['Idempotency-Key']),
    );
  });

  test('crearNotificacion devuelve la venta con telefono_final', () async {
    final mock = MockVentaApi(crearDioVenta());
    mock.alCrearNotificacion(201, cuerpoNotificacion(id: 3));
    final venta = await VentaRepository(mock.dio)
        .crearNotificacion(monto: '120', telefono: '5512344321');
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
    mock.alCrearNotificacion(409, {
      'codigo': 'CUENTA_NO_ACTIVE',
      'detail': 'La cuenta no está ACTIVE.',
    });
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
      VentaRepository(mock.dio).crearNotificacion(monto: '1', telefono: '123'),
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
