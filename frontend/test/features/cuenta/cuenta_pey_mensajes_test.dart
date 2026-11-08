import 'package:cody/features/cuenta/data/cuenta_estado.dart';
import 'package:cody/features/cuenta/presentation/cuenta_pey_mensajes.dart';
import 'package:cody/features/cobro/presentation/qr_general_impreso_page.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const pendienteRegistro = EstadoCuentaPey(
    fase: 'pendiente_registro',
    paso: 2,
    codiStatus: 'pending',
    puedeCobrar: false,
    clabeEnmascarada: '**************5713',
    tieneCuentaPey: false,
    peyBankAccountIdSufijo: '',
  );

  test('paso 2 tiene mensaje de registro en pey', () {
    expect(tituloBloqueoCuenta(pendienteRegistro), contains('pey'));
    expect(mensajeSiguientePaso(pendienteRegistro), contains('Paso 2'));
  });

  test('sin estado usa el mensaje clásico de Mi QR', () {
    expect(tituloBloqueoCuenta(null), kMensajeCuentaNoActivaQr);
  });

  test('paso 1 y 3 cubren bordes de CLABE y activación', () {
    const sinClabe = EstadoCuentaPey(
      fase: 'sin_clabe',
      paso: 1,
      codiStatus: 'pending',
      puedeCobrar: false,
      clabeEnmascarada: '',
      tieneCuentaPey: false,
      peyBankAccountIdSufijo: '',
    );
    const paso3 = EstadoCuentaPey(
      fase: 'pendiente_activacion',
      paso: 3,
      codiStatus: 'pending',
      puedeCobrar: false,
      clabeEnmascarada: '**************5713',
      tieneCuentaPey: true,
      peyBankAccountIdSufijo: 'Q0P',
    );
    expect(mensajeSiguientePaso(sinClabe), contains('Paso 1'));
    expect(mensajeSiguientePaso(paso3), contains('Paso 3'));
  });
}
