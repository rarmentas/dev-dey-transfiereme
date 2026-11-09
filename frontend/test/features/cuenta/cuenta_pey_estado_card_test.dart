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

const _activa = EstadoCuentaPey(
  fase: 'activa',
  paso: null,
  codiStatus: 'active',
  puedeCobrar: true,
  clabeEnmascarada: '**************3553',
  tieneCuentaPey: true,
  peyBankAccountIdSufijo: 'PADD',
);

class _RepoControlado extends CuentaEstadoRepository {
  _RepoControlado(this.resultado) : super(Dio(BaseOptions(baseUrl: 'http://test')));

  EstadoCuentaPey resultado;
  Object? error;
  var llamadas = 0;

  @override
  Future<EstadoCuentaPey> sincronizar() async {
    llamadas++;
    if (error != null) {
      throw error!;
    }
    return resultado;
  }
}

Future<void> _montar(WidgetTester tester, _RepoControlado repo) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        cuentaEstadoProvider.overrideWith((ref) async => _pendiente),
        cuentaEstadoRepositoryProvider.overrideWithValue(repo),
      ],
      child: MaterialApp(
        theme: TfTheme.light,
        home: const Scaffold(body: CuentaPeyEstadoCard(compacto: true)),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('la tarjeta pending conserva Revisar estado y no explica los 5 días', (
    tester,
  ) async {
    await _montar(tester, _RepoControlado(_pendiente));

    expect(find.text('Revisar estado'), findsOneWidget);
    expect(find.byIcon(Icons.sync_rounded), findsOneWidget);
    expect(find.text('Verificar'), findsNothing);
    expect(find.textContaining('5 días hábiles'), findsNothing);
    expect(find.textContaining('Pendiente de activación'), findsWidgets);
  });

  testWidgets('si sigue pendiente, el detalle sale después de sincronizar', (
    tester,
  ) async {
    final repo = _RepoControlado(_pendiente);
    await _montar(tester, repo);

    await tester.tap(find.text('Revisar estado'));
    await tester.pumpAndSettle();

    expect(repo.llamadas, 1);
    expect(find.text('Activación de tu CLABE'), findsOneWidget);
    expect(find.textContaining('····3553'), findsOneWidget);
    expect(find.textContaining('5 días hábiles'), findsOneWidget);
    expect(find.byKey(const Key('revisar_estado_activacion')), findsNothing);

    await tester.tap(find.byKey(const Key('cerrar_activacion_clabe')));
    await tester.pumpAndSettle();

    expect(find.text('Activación de tu CLABE'), findsNothing);
    expect(find.text('Revisar estado'), findsOneWidget);
    expect(find.byIcon(Icons.sync_rounded), findsOneWidget);
  });

  testWidgets('si queda activa, avisa y no abre el detalle', (tester) async {
    final repo = _RepoControlado(_activa);
    await _montar(tester, repo);

    await tester.tap(find.text('Revisar estado'));
    await tester.pumpAndSettle();

    expect(repo.llamadas, 1);
    expect(find.text('Tu cuenta ya está activa para cobrar.'), findsOneWidget);
    expect(find.text('Activación de tu CLABE'), findsNothing);
  });

  testWidgets('si la sincronización falla, no abre el detalle', (tester) async {
    final repo = _RepoControlado(_pendiente)
      ..error = CuentaPeyApiException('Espere antes de volver a sincronizar.');
    await _montar(tester, repo);

    await tester.tap(find.text('Revisar estado'));
    await tester.pumpAndSettle();

    expect(find.text('Espere antes de volver a sincronizar.'), findsOneWidget);
    expect(find.text('Activación de tu CLABE'), findsNothing);
  });
}
