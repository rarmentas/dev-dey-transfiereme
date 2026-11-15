import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:cody/features/pedidos/data/pedido_repository.dart';
import 'package:cody/features/pedidos/presentation/catalogo_page.dart';
import 'package:cody/features/pedidos/presentation/pedido_providers.dart';

import '../../support/mock_pedido_api.dart';

class CatalogoFalso extends PedidoRepository {
  CatalogoFalso() : super(crearDioPedido());
  bool habilitado = false;
  @override
  Future<Map<String, dynamic>> catalogo() async => {
    'agente_habilitado': habilitado,
    'es_dueno': true,
    'productos': [
      {
        'id': 1,
        'nombre': 'tortilla',
        'alias': ['tortillas'],
        'unidad': 'kg',
        'precio_centavos': 2500,
        'disponible': true,
      },
    ],
  };
  @override
  Future<Map<String, dynamic>> configurarAgente(bool valor) async {
    habilitado = valor;
    return {'agente_habilitado': valor};
  }
}

void main() {
  testWidgets('lista de precios y activación del comercio', (tester) async {
    final repo = CatalogoFalso();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [pedidoRepositoryProvider.overrideWithValue(repo)],
        child: const MaterialApp(home: CatalogoPage()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('tortilla'), findsOneWidget);
    expect(find.text('kg · \$25.00'), findsOneWidget);
    await tester.tap(find.byType(SwitchListTile));
    await tester.pumpAndSettle();
    expect(repo.habilitado, isTrue);
  });
}
