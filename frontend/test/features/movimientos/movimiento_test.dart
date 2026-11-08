import 'package:cody/features/movimientos/data/movimiento.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('fromJson conserva el monto y lee pagado_en presente', () {
    final movimiento = Movimiento.fromJson({
      'id': 7,
      'monto': '0.01',
      'concepto_visible': 'Tacos al pastor',
      'canal': 'qr_general',
      'estado': 'pagado',
      'origen': 'origen_pey',
      'creado_en': '2026-11-07T18:00:00Z',
      'pagado_en': '2026-11-07T18:05:00Z',
    });

    expect(movimiento.monto, '0.01');
    expect(movimiento.monto, isA<String>());
    expect(movimiento.montoFormateado, r'$0.01');
    expect(movimiento.pagadoEn, DateTime.parse('2026-11-07T18:05:00Z'));
    expect(movimiento.creadoEn, DateTime.parse('2026-11-07T18:00:00Z'));
    expect(movimiento.fechaMostrada, movimiento.pagadoEn);
    expect(movimiento.esPrueba, isFalse);
    expect(movimiento.etiquetaCanal, 'QR general');
    expect(movimiento.etiquetaEstado, 'Pagado');
    expect(movimiento.concepto, 'Tacos al pastor');
    expect(movimiento.muestraEnviado, isFalse);
  });

  test('concepto enviado distinto del visible se conserva', () {
    final movimiento = Movimiento.fromJson({
      'id': 11,
      'monto': '0.01',
      'concepto': 'Transferencia',
      'concepto_visible': 'Tortas',
      'canal': 'qr_venta',
      'estado': 'pagado',
      'origen': 'origen_pey',
      'creado_en': '2026-11-07T18:00:00Z',
      'pagado_en': '2026-11-07T18:05:00Z',
    });

    expect(movimiento.concepto, 'Transferencia');
    expect(movimiento.conceptoVisible, 'Tortas');
    expect(movimiento.muestraEnviado, isTrue);
  });

  test('fromJson acepta pagado_en nulo', () {
    final movimiento = Movimiento.fromJson({
      'id': 8,
      'monto': '10.00',
      'concepto_visible': 'Refresco',
      'canal': 'qr_venta',
      'estado': 'pendiente',
      'origen': 'origen_desarrollo',
      'creado_en': '2026-11-06T18:00:00Z',
      'pagado_en': null,
    });

    expect(movimiento.pagadoEn, isNull);
    expect(movimiento.fechaMostrada, movimiento.creadoEn);
    expect(movimiento.esPrueba, isTrue);
    expect(movimiento.etiquetaCanal, 'QR de venta');
    expect(movimiento.etiquetaEstado, 'Pendiente');
    expect(movimiento.montoFormateado, r'$10.00');
  });

  test('separa miles sin pasar el monto por double', () {
    final movimiento = Movimiento.fromJson({
      'id': 9,
      'monto': '1234.50',
      'concepto_visible': 'Aviso',
      'canal': 'notificacion',
      'estado': 'vencido',
      'origen': 'origen_pey',
      'creado_en': '2026-11-05T18:00:00Z',
      'pagado_en': null,
    });

    expect(movimiento.monto, '1234.50');
    expect(movimiento.montoFormateado, r'$1,234.50');
    expect(movimiento.etiquetaCanal, 'Notificación');
    expect(movimiento.etiquetaEstado, 'Vencido');
  });
}
