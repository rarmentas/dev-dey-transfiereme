import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:cody/features/pedidos/data/pedido_repository.dart';
import 'package:cody/features/pedidos/presentation/pedido_providers.dart';
import 'package:cody/features/pedidos/presentation/pedidos_page.dart';

import '../../support/mock_pedido_api.dart';

void main() {
  testWidgets('muestra vacío y actualizar', (tester) async {
    final mock = MockPedidoApi(crearDioPedido());
    mock.responder('GET', '/api/pedidos/', 200, exito({'pedidos': []}));
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          pedidoRepositoryProvider.overrideWithValue(
            PedidoRepository(mock.dio),
          ),
        ],
        child: const MaterialApp(home: PedidosPage()),
      ),
    );
    await tester.pumpAndSettle();
    expect(
      find.text(
        'Aún no hay pedidos. Cuando un cliente pida por WhatsApp aparecerá aquí.',
      ),
      findsOneWidget,
    );
    expect(find.text('Actualizar'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('muestra pedido y total del servidor', (tester) async {
    final mock = MockPedidoApi(crearDioPedido());
    mock.responder(
      'GET',
      '/api/pedidos/',
      200,
      exito({
        'pedidos': [
          {
            'id': 'abc',
            'numero': 7,
            'estado': 'cotizado',
            'cliente_etiqueta': '1234',
            'renglones_pendientes': 0,
            'total_comercial_centavos': 1250,
          },
        ],
      }),
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          pedidoRepositoryProvider.overrideWithValue(
            PedidoRepository(mock.dio),
          ),
        ],
        child: const MaterialApp(home: PedidosPage()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('Pedido #7'), findsOneWidget);
    expect(find.textContaining(r'$12.50'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
}
