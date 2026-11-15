import 'package:cody/features/pedidos/data/pedido.dart';
import 'package:cody/features/pedidos/presentation/widgets/entrega_card.dart';
import 'package:cody/features/pedidos/presentation/widgets/pago_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../support/mock_pedido_api.dart';

void main() {
  final estados = {
    'en_espera': 'Cobro en espera',
    'reservado': 'Generando cobro…',
    'enviando': 'Generando cobro…',
    'pendiente': 'Pago pendiente',
    'incierto': 'Cobro no confirmado. No lo repitas.',
    'pagado': 'Pagado',
    'descartado': 'Cobro descartado. Publica y acepta de nuevo.',
    'rechazado': 'Cobro rechazado',
    'vencido': 'Cobro vencido',
  };
  Widget pagoCard(Map<String, dynamic> json, TextEditingController telefono) =>
      MaterialApp(
        home: Scaffold(
          body: PagoCard(
            pedido: Pedido.fromJson(json),
            ocupado: false,
            cobrar: () {},
            activar: () {},
            telefono: telefono,
            canal: 'qr_venta',
            cambiarCanal: (_) {},
          ),
        ),
      );
  for (final entrada in estados.entries) {
    testWidgets('estado de pago ${entrada.key}', (t) async {
      final json = pedidoJson(aceptado: true);
      json['pago_estado'] = entrada.key;
      json['intento'] = {'intento_id': 'i1', 'aceptacion_id': 'a'};
      final telefono = TextEditingController();
      addTearDown(telefono.dispose);
      await t.pumpWidget(pagoCard(json, telefono));
      expect(find.text(entrada.value), findsOneWidget);
      expect(find.text('Cobrar'), findsNothing);
      expect(
        find.text('Activar cobro'),
        entrada.key == 'en_espera' ? findsOneWidget : findsNothing,
      );
    });
  }
  for (final estado in ['descartado', 'rechazado', 'vencido']) {
    testWidgets('$estado de otra aceptacion permite cobrar la vigente', (
      t,
    ) async {
      final json = pedidoJson(aceptado: true);
      json['pago_estado'] = estado;
      json['intento'] = {'intento_id': 'i1', 'aceptacion_id': 'anterior'};
      final telefono = TextEditingController();
      addTearDown(telefono.dispose);
      await t.pumpWidget(pagoCard(json, telefono));
      expect(find.text('Sin cobro'), findsOneWidget);
      expect(
        find.text('Cobro anterior: ${etiquetaPago(estado)}'),
        findsOneWidget,
      );
      expect(find.text('Cobrar'), findsOneWidget);
    });
  }
  for (final estado in ['incierto', 'pendiente', 'reservado', 'pagado']) {
    testWidgets('$estado de otra aceptacion no permite cobrar', (t) async {
      final json = pedidoJson(aceptado: true);
      json['pago_estado'] = estado;
      json['intento'] = {'intento_id': 'i1', 'aceptacion_id': 'anterior'};
      final telefono = TextEditingController();
      addTearDown(telefono.dispose);
      await t.pumpWidget(pagoCard(json, telefono));
      expect(find.text(estados[estado]!), findsOneWidget);
      expect(find.text('Cobrar'), findsNothing);
    });
  }
  testWidgets('descartado sin aceptacion conocida no permite cobrar', (
    t,
  ) async {
    final json = pedidoJson(aceptado: true);
    json['pago_estado'] = 'descartado';
    json['intento'] = {'intento_id': 'i1'};
    final telefono = TextEditingController();
    addTearDown(telefono.dispose);
    await t.pumpWidget(pagoCard(json, telefono));
    expect(find.text('Cobrar'), findsNothing);
  });

  testWidgets('pendiente muestra QR y vencimiento', (t) async {
    final json = pedidoJson(aceptado: true);
    json['pago_estado'] = 'pendiente';
    json['intento'] = {'qr': 'QR-123', 'vencimiento': 'mañana'};
    final telefono = TextEditingController();
    addTearDown(telefono.dispose);
    await t.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: PagoCard(
            pedido: Pedido.fromJson(json),
            ocupado: false,
            cobrar: () {},
            activar: () {},
            telefono: telefono,
            canal: 'qr_venta',
            cambiarCanal: (_) {},
          ),
        ),
      ),
    );
    expect(find.byType(QrImageView), findsOneWidget);
    expect(find.text('Vence: mañana'), findsOneWidget);
  });

  testWidgets('sin pago listo está deshabilitado; pagado lo habilita', (
    t,
  ) async {
    final json = pedidoJson(aceptado: true);
    Widget tarjeta() => MaterialApp(
      home: Scaffold(
        body: EntregaCard(
          pedido: Pedido.fromJson(json),
          ocupado: false,
          listo: () {},
          entregado: () {},
        ),
      ),
    );
    await t.pumpWidget(tarjeta());
    expect(
      t
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Marcar listo'),
          )
          .onPressed,
      isNull,
    );
    json['pago_estado'] = 'pagado';
    await t.pumpWidget(tarjeta());
    expect(
      t
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Marcar listo'),
          )
          .onPressed,
      isNotNull,
    );
    json['preparacion'] = 'listo';
    json['entrega'] = {'listo_por': 'Ana', 'listo_en': '2026-01-01'};
    await t.pumpWidget(tarjeta());
    expect(find.textContaining('Ana'), findsOneWidget);
    expect(find.text('Marcar entregado'), findsOneWidget);
  });
}
