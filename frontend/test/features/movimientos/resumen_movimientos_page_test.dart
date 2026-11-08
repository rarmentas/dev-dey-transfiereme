import 'package:cody/features/movimientos/data/movimientos_repository.dart';
import 'package:cody/features/movimientos/presentation/movimientos_providers.dart';
import 'package:cody/features/movimientos/presentation/resumen_movimientos_page.dart';
import 'package:cody/theme/transfiereme_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/mock_movimientos_api.dart';

Future<void> _montar(
  WidgetTester tester,
  MockMovimientosApi mock, {
  bool semana = true,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        movimientosRepositoryProvider.overrideWith(
          (ref) => MovimientosRepository(mock.dio),
        ),
        movimientosAhoraProvider.overrideWithValue(DateTime(2026, 11, 7, 20)),
      ],
      child: MaterialApp(
        theme: TfTheme.light,
        home: const ResumenMovimientosPage(),
      ),
    ),
  );
  await _esperar(tester);
  if (semana) await _verSemana(tester);
}

Future<void> _verSemana(WidgetTester tester) async {
  await tester.tap(find.text('Semana'));
  await tester.pump();
}

/// Riverpod 3 agenda el trabajo del provider en un temporizador de duración
/// cero. `pump` sin duración no lo dispara.
Future<void> _esperar(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 1));
  await tester.pump();
}

void main() {
  test('el mock responde el listado', () async {
    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.responderLista(fixtureTresCanales());
    final lista = await MovimientosRepository(mock.dio).listar();
    expect(lista, hasLength(3));
    expect(lista.first.conceptoVisible, 'Tacos al pastor');
  });

  testWidgets('lista los tres canales con monto exacto', (tester) async {
    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.responderLista(fixtureTresCanales());

    await _montar(tester, mock);

    expect(find.text('Movimientos'), findsOneWidget);
    expect(find.text('Tacos al pastor'), findsOneWidget);
    expect(find.text('Refresco'), findsOneWidget);
    expect(find.text('Agua natural'), findsOneWidget);
    expect(find.textContaining('QR general'), findsOneWidget);
    expect(find.textContaining('QR de venta'), findsOneWidget);
    expect(find.textContaining('Notificación'), findsOneWidget);
    // 3 montos + el total del día pagado.
    expect(find.text(r'$0.01'), findsNWidgets(4));
    expect(find.text('Pagado'), findsOneWidget);
    expect(find.text('Pendiente'), findsOneWidget);
    expect(find.text('Vencido'), findsOneWidget);
    expect(find.text('Prueba'), findsOneWidget);
    expect(find.byType(RefreshIndicator), findsOneWidget);
    expect(tester.getSize(find.byType(ListView)).width, 480);
  });

  testWidgets('lista vacía muestra el texto de vacío', (tester) async {
    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.responderVacio();

    await _montar(tester, mock, semana: false);

    expect(find.text('Aún no tienes cobros'), findsOneWidget);
    expect(find.text('Cobra y aquí verás cada pago.'), findsOneWidget);
    expect(find.text('Prueba'), findsNothing);
  });

  testWidgets('error 500 muestra mensaje y Reintentar vuelve a pedir', (
    tester,
  ) async {
    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.responderError(500);

    await _montar(tester, mock, semana: false);

    expect(
      find.text(
        'El servidor no está disponible en este momento. Intenta de nuevo más tarde.',
      ),
      findsOneWidget,
    );
    expect(find.text('Reintentar'), findsOneWidget);
    expect(mock.llamadas, 1);

    mock.responderLista(fixtureTresCanales());
    await tester.tap(find.text('Reintentar'));
    await _esperar(tester);
    await _verSemana(tester);

    expect(mock.llamadas, 2);
    expect(find.text('Tacos al pastor'), findsOneWidget);
    expect(find.text('Refresco'), findsOneWidget);
    expect(find.text('Agua natural'), findsOneWidget);
    expect(find.text('Prueba'), findsOneWidget);
  });

  testWidgets('el filtro Hoy/Semana/Mes filtra por fecha local', (
    tester,
  ) async {
    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.responderLista(fixtureTresCanales());

    await _montar(tester, mock);
    await tester.tap(find.text('Hoy'));
    await tester.pump();

    expect(find.text('Tacos al pastor'), findsOneWidget);
    expect(find.text('Refresco'), findsNothing);
    expect(find.textContaining('HOY · 1 COBRO'), findsOneWidget);
    expect(find.text(r'$0.01'), findsNWidgets(2));

    await tester.tap(find.text('Mes'));
    await tester.pump();
    expect(find.text('Agua natural'), findsOneWidget);
    expect(find.textContaining('VIE 06 NOV · 1 COBRO'), findsOneWidget);
  });

  testWidgets('el total del día excluye los pagados de prueba', (tester) async {
    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.responderLista([
      {
        'id': 1,
        'monto': '10.00',
        'concepto_visible': 'Tacos al pastor',
        'canal': 'qr_general',
        'estado': 'pagado',
        'origen': 'origen_pey',
        'creado_en': '2026-11-07T18:00:00Z',
        'pagado_en': '2026-11-07T18:05:00Z',
      },
      {
        'id': 2,
        'monto': '28.50',
        'concepto_visible': 'Refresco',
        'canal': 'notificacion',
        'estado': 'pagado',
        'origen': 'origen_desarrollo',
        'creado_en': '2026-11-07T14:00:00Z',
        'pagado_en': '2026-11-07T14:22:00Z',
      },
    ]);

    await _montar(tester, mock, semana: false);

    expect(find.textContaining('HOY · 2 COBROS'), findsOneWidget);
    expect(find.text(r'$10.00'), findsNWidgets(2));
    expect(find.text(r'$28.50'), findsOneWidget);
    expect(find.text(r'$38.50'), findsNothing);
  });

  testWidgets('a 360 dp la hora y el canal no se cortan', (tester) async {
    final loader = FontLoader('Inter')
      ..addFont(rootBundle.load('assets/fonts/Inter-Regular.ttf'))
      ..addFont(rootBundle.load('assets/fonts/Inter-Medium.ttf'))
      ..addFont(rootBundle.load('assets/fonts/Inter-SemiBold.ttf'));
    await loader.load();

    await tester.binding.setSurfaceSize(const Size(360, 800));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.responderLista(fixtureTresCanales());
    await _montar(tester, mock);

    for (final canal in ['QR general', 'QR de venta', 'Notificación']) {
      final parrafo = tester.renderObject<RenderParagraph>(
        find.textContaining(canal),
      );
      expect(parrafo.didExceedMaxLines, isFalse, reason: canal);
    }
    expect(find.text('Prueba'), findsOneWidget);
    expect(find.byType(Chip), findsNothing);
  });

  testWidgets('la etiqueta Prueba va junto al concepto y no se toca', (
    tester,
  ) async {
    final mock = MockMovimientosApi(crearDioMovimientos());
    mock.responderLista(fixtureTresCanales());

    await _montar(tester, mock);

    expect(find.text('Prueba'), findsOneWidget);
    expect(find.byType(Chip), findsNothing);
    expect(
      find.ancestor(of: find.text('Prueba'), matching: find.byType(InkWell)),
      findsNothing,
    );

    final texto = tester.widget<Text>(find.text('Prueba'));
    expect(texto.data, 'Prueba');
    final caja = tester.getSize(
      find
          .ancestor(of: find.text('Prueba'), matching: find.byType(Container))
          .first,
    );
    expect(caja.height, 20);

    Element? filaDe(String texto) {
      Element? fila;
      find.text(texto).evaluate().single.visitAncestorElements((element) {
        if (element.widget is Row) {
          fila = element;
          return false;
        }
        return true;
      });
      return fila;
    }

    expect(filaDe('Prueba'), filaDe('Refresco'));
    expect(filaDe('Prueba'), isNot(filaDe('Pagado')));

    final tarjetaPrueba = find.ancestor(
      of: find.text('Prueba'),
      matching: find.byType(Card),
    );
    expect(
      find.descendant(of: tarjetaPrueba, matching: find.text('Refresco')),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: tarjetaPrueba,
        matching: find.text('Tacos al pastor'),
      ),
      findsNothing,
    );
    expect(
      find.descendant(of: tarjetaPrueba, matching: find.text('Agua natural')),
      findsNothing,
    );
  });
}
