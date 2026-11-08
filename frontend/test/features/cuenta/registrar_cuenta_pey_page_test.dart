import 'package:cody/features/cuenta/data/cuenta_estado.dart';
import 'package:cody/features/cuenta/data/cuenta_estado_repository.dart';
import 'package:cody/features/cuenta/presentation/registrar_cuenta_pey_page.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
class _RepoFalso extends CuentaEstadoRepository {
  _RepoFalso() : super(Dio());

  var llamadas = 0;
  var ultimoReemplazar = false;

  @override
  Future<EstadoCuentaPey> registrarEnPey({
    required String nombre,
    required String entidad,
    String alias = '',
    bool reemplazar = false,
  }) async {
    llamadas++;
    ultimoReemplazar = reemplazar;
    if (!reemplazar) {
      throw CuentaPeyApiException(
        'Ya registrada',
        codigo: 'CUENTA_PEY_YA_REGISTRADA',
      );
    }
    return const EstadoCuentaPey(
      fase: 'pendiente_activacion',
      paso: 3,
      codiStatus: 'pending',
      puedeCobrar: false,
      clabeEnmascarada: '**************5713',
      tieneCuentaPey: true,
      peyBankAccountIdSufijo: 'Q0M',
    );
  }
}

void main() {
  testWidgets('409 exige confirmación antes de reemplazar', (tester) async {
    final repo = _RepoFalso();
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          theme: TfTheme.light,
          home: Builder(
            builder: (context) => Scaffold(
              body: Center(
                child: FilledButton(
                  onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => RegistrarCuentaPeyPage(repositorio: repo),
                    ),
                  ),
                  child: const Text('Abrir'),
                ),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Abrir'));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const Key('campo_nombre_titular')),
      'Ana López',
    );
    await tester.tap(find.byKey(const Key('boton_enviar_registro_pey')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('¿Reemplazar la cuenta en pey?'), findsOneWidget);
    await tester.tap(find.byKey(const Key('confirmar_reemplazo_pey')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(repo.llamadas, 2);
    expect(repo.ultimoReemplazar, isTrue);
  });
}
