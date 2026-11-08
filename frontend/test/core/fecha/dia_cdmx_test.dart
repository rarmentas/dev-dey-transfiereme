import 'package:cody/core/fecha/dia_cdmx.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('23:30 CDMX es 05:30Z del día siguiente y sigue siendo hoy', () {
    final instante = DateTime.utc(2026, 11, 8, 5, 30);
    expect(diaCdmx(instante), DateTime(2026, 11, 7));
    expect(horaCdmx(instante), '23:30');
    final c = ahoraCdmx(instante);
    expect((c.year, c.month, c.day, c.hour, c.minute), (2026, 11, 7, 23, 30));
  });

  test('a las 06:00Z ya es el día nuevo en CDMX', () {
    expect(diaCdmx(DateTime.utc(2026, 11, 8, 6)), DateTime(2026, 11, 8));
    expect(diaCdmx(DateTime.utc(2026, 11, 8, 5, 59)), DateTime(2026, 11, 7));
  });

  test('el corte de semana es el lunes', () {
    // Domingo 8 nov 2026 en CDMX.
    expect(lunesDe(DateTime(2026, 11, 8)), DateTime(2026, 11, 2));
    // Lunes 2 nov a las 00:30 CDMX (06:30Z) abre semana nueva.
    final lunes = diaCdmx(DateTime.utc(2026, 11, 2, 6, 30));
    expect(lunesDe(lunes), DateTime(2026, 11, 2));
    // Domingo 1 nov 23:30 CDMX (05:30Z del lunes) sigue en la semana previa.
    final domingo = diaCdmx(DateTime.utc(2026, 11, 2, 5, 30));
    expect(domingo, DateTime(2026, 11, 1));
    expect(lunesDe(domingo), DateTime(2026, 10, 26));
  });

  test('cruza el cambio de mes con el desfase', () {
    expect(diaCdmx(DateTime.utc(2026, 12, 1, 5)), DateTime(2026, 11, 30));
  });
}
