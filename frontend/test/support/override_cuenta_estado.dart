import 'package:cody/features/cuenta/data/cuenta_estado.dart';
import 'package:cody/features/cuenta/presentation/cuenta_providers.dart';
import 'package:flutter_riverpod/misc.dart';

const estadoCuentaActivaPrueba = EstadoCuentaPey(
  fase: 'activa',
  paso: null,
  codiStatus: 'active',
  puedeCobrar: true,
  clabeEnmascarada: '**************5713',
  tieneCuentaPey: true,
  peyBankAccountIdSufijo: 'Q0P',
);

Override cuentaEstadoActivaOverride() {
  return cuentaEstadoProvider.overrideWith((ref) async => estadoCuentaActivaPrueba);
}
