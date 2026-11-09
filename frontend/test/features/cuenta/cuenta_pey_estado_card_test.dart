import 'package:cody/features/cuenta/data/cuenta_estado.dart';
import 'package:cody/features/cuenta/data/cuenta_estado_repository.dart';
import 'package:cody/features/cuenta/presentation/cuenta_providers.dart';
import 'package:cody/features/cuenta/presentation/widgets/cuenta_pey_estado_card.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _pendiente = EstadoCuentaPey(
  fase: 'pendiente_activacion',
  paso: 3,
  codiStatus: 'pending',
  puedeCobrar: false,
  clabeEnmascarada: '**************3553',
  tieneCuentaPey: true,
  peyBankAccountIdSufijo: 'PADD',
);

class _RepoQuieto extends CuentaEstadoRepository {
  _RepoQuieto() : super(Dio(BaseOptions(baseUrl: 'http://test')));

  @override
  Future<EstadoCuentaPey> sincronizar() async => _pendiente;
}

void main() {
  testWidgets('Verificar abre el detalle y Cerrar lo quita de la vista', (
    tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          cuentaEstadoProvider.overrideWith((ref) async => _pendiente),
          cuentaEstadoRepositoryProvider.overrideWithValue(_RepoQuieto()),
        ],
        child: MaterialApp(
          theme: TfTheme.light,
          home: const Scaffold(body: CuentaPeyEstadoCard(compacto: true)),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('5 días hábiles'), findsNothing);
    expect(find.text('Verificar'), findsOneWidget);

    await tester.tap(find.text('Verificar'));
    await tester.pumpAndSettle();

    expect(find.text('Activación de tu CLABE'), findsOneWidget);
    expect(find.textContaining('····3553'), findsOneWidget);
    expect(find.textContaining('5 días hábiles'), findsOneWidget);

    await tester.tap(find.byKey(const Key('cerrar_activacion_clabe')));
    await tester.pumpAndSettle();

    expect(find.text('Activación de tu CLABE'), findsNothing);
    expect(find.text('Verificar'), findsOneWidget);
  });
}
