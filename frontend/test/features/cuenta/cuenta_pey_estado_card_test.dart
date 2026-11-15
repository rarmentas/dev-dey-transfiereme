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

class _RepoControlado extends CuentaEstadoRepository {
  _RepoControlado() : super(Dio(BaseOptions(baseUrl: 'http://test')));
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
  testWidgets(
    'la tarjeta pending conserva Revisar estado y no explica los 5 días',
    (tester) async {
      await _montar(tester, _RepoControlado());

      expect(find.text('Revisar estado'), findsOneWidget);
      expect(find.byIcon(Icons.sync_rounded), findsOneWidget);
      expect(find.text('Verificar'), findsNothing);
      expect(find.textContaining('5 días hábiles'), findsNothing);
      expect(find.textContaining('Pendiente de activación'), findsWidgets);
    },
  );
}
