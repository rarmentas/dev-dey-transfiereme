import 'package:cody/features/cuenta/data/cuenta_cobro.dart';
import 'package:cody/features/cuenta/data/cuentas_repository.dart';
import 'package:cody/features/cuenta/presentation/cuentas_page.dart';
import 'package:cody/features/cuenta/presentation/cuentas_providers.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

CuentaCobro cuenta({String registro = 'sin_registro', bool apta = false}) =>
    CuentaCobro.fromJson({
      'id': '1',
      'clabe_enmascarada': '000000000000001234',
      'registro_estado': registro,
      'codi_status': apta ? 'active' : 'pending',
      'puede_cobrar': apta,
      'version': 3,
    });

class RepoCuentas extends CuentasRepository {
  RepoCuentas() : super(Dio());
  List<CuentaCobro> lista = [];
  CuentasException? errorLista, errorAccion;
  int lecturas = 0, altas = 0, registros = 0, syncs = 0, defaults = 0;
  @override
  Future<List<CuentaCobro>> listar() async {
    lecturas++;
    if (errorLista != null) throw errorLista!;
    return List.of(lista);
  }

  @override
  Future<CuentaCobro> crear(String clabe) async {
    altas++;
    if (errorAccion != null) throw errorAccion!;
    final nueva = cuenta();
    lista.add(nueva);
    return nueva;
  }

  @override
  Future<CuentaCobro> registrar(
    String id,
    String nombre,
    String entidad,
    String alias,
    int versionEsperada,
  ) async {
    registros++;
    if (errorAccion != null) throw errorAccion!;
    expect(
      [id, nombre, entidad, alias, versionEsperada],
      ['1', 'Ana', 'PERSON', '', 3],
    );
    lista = [cuenta(registro: 'registrado')];
    return lista.single;
  }

  @override
  Future<CuentaCobro> sincronizar(String id) async {
    syncs++;
    if (errorAccion != null) throw errorAccion!;
    return lista.single;
  }

  @override
  Future<CuentaCobro> elegirPredeterminada(
    String id,
    int versionEsperada,
  ) async {
    defaults++;
    expect([id, versionEsperada], ['1', 3]);
    if (errorAccion != null) throw errorAccion!;
    return lista.single;
  }
}

Future<void> abrir(WidgetTester t, RepoCuentas repo) async {
  await t.pumpWidget(
    ProviderScope(
      overrides: [cuentasRepositoryProvider.overrideWithValue(repo)],
      child: const MaterialApp(home: CuentasPage()),
    ),
  );
  await t.pumpAndSettle();
}

Future<void> alta(WidgetTester t) async {
  await t.enterText(
    find.widgetWithText(TextField, 'CLABE'),
    '000000000000000000',
  );
  await t.tap(find.text('Agregar cuenta'));
  await t.pumpAndSettle();
}

Future<void> registrar(WidgetTester t) async {
  await t.tap(find.widgetWithText(OutlinedButton, 'Registrar'));
  await t.pumpAndSettle();
  await t.enterText(find.widgetWithText(TextField, 'Nombre'), 'Ana');
  await t.tap(find.widgetWithText(TextButton, 'Registrar'));
  await t.pumpAndSettle();
}

void main() {
  testWidgets(
    'alta agrega cuenta limpia campo y nunca muestra CLABE completa',
    (t) async {
      final repo = RepoCuentas();
      await abrir(t, repo);
      await alta(t);
      expect(repo.altas, 1);
      expect(find.text('••••1234'), findsOneWidget);
      expect(find.text('000000000000001234'), findsNothing);
      expect(
        t
            .widget<TextField>(find.widgetWithText(TextField, 'CLABE'))
            .controller!
            .text,
        isEmpty,
      );
    },
  );
  for (final codigo in ['CLABE_INVALIDA', 'CLABE_DUPLICADA']) {
    testWidgets('$codigo deja formulario editable', (t) async {
      final repo = RepoCuentas()
        ..errorAccion = CuentasException(
          codigo,
          codigo == 'CLABE_INVALIDA' ? 400 : 409,
          codigo == 'CLABE_INVALIDA'
              ? 'La CLABE no es válida.'
              : 'Ya está guardada.',
        );
      await abrir(t, repo);
      await alta(t);
      expect(repo.altas, 1);
      expect(
        find.text(
          codigo == 'CLABE_INVALIDA'
              ? 'La CLABE no es válida.'
              : 'Ya está guardada.',
        ),
        findsWidgets,
      );
      expect(
        t
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Agregar cuenta'),
            )
            .onPressed,
        isNotNull,
      );
      expect(
        t.widget<TextField>(find.widgetWithText(TextField, 'CLABE')).enabled,
        isTrue,
      );
    });
  }
  for (final status in [401, 403]) {
    testWidgets('$status no ofrece acciones', (t) async {
      final repo = RepoCuentas()
        ..errorLista = CuentasException(
          status == 403 ? 'NO_ES_DUENO' : 'SESION_TERMINADA',
          status,
          status == 403
              ? 'Solo el dueño administra cuentas.'
              : 'Tu sesión terminó. Vuelve a entrar.',
        );
      await abrir(t, repo);
      expect(
        find.text(
          status == 403
              ? 'Solo el dueño administra cuentas.'
              : 'Tu sesión terminó. Vuelve a entrar.',
        ),
        findsOneWidget,
      );
      expect(find.text('Agregar cuenta'), findsNothing);
    });
  }

  testWidgets('error inicial permite reintentar carga', (t) async {
    final repo = RepoCuentas()
      ..errorLista = CuentasException('ERROR', 503, 'Error del servidor');
    await abrir(t, repo);
    expect(find.text('Error del servidor'), findsOneWidget);
    repo.errorLista = null;
    await t.tap(find.text('Reintentar'));
    await t.pumpAndSettle();
    expect(repo.lecturas, 2);
    expect(find.text('Aún no tienes cuentas'), findsOneWidget);
    expect(find.text('Error del servidor'), findsNothing);
  });

  for (final estado in ['registrando', 'incierto']) {
    testWidgets('$estado no ofrece registrar', (t) async {
      final repo = RepoCuentas()..lista = [cuenta(registro: estado)];
      await abrir(t, repo);
      expect(find.text('Registrar'), findsNothing);
      expect(find.text('Sincronizar'), findsOneWidget);
    });
  }
  testWidgets('registro exitoso actualiza la cuenta', (t) async {
    final repo = RepoCuentas()..lista = [cuenta()];
    await abrir(t, repo);
    await registrar(t);
    expect(repo.registros, 1);
    expect(find.textContaining('Registrada'), findsOneWidget);
    expect(find.text('Registrar'), findsNothing);
  });
  testWidgets(
    'registro incierto no ofrece repetir aun si la recarga queda atrasada',
    (t) async {
      final repo = RepoCuentas()
        ..lista = [cuenta()]
        ..errorAccion = CuentasException(
          'REGISTRO_INCIERTO',
          409,
          'Registro no confirmado',
        );
      await abrir(t, repo);
      await registrar(t);
      expect(repo.registros, 1);
      expect(repo.lecturas, 2);
      expect(find.text('Registrar'), findsNothing);
      expect(find.text('Sincronizar'), findsOneWidget);
    },
  );
  for (final codigo in [
    'CUENTA_NO_ENCONTRADA',
    'CUENTA_NO_ELEGIBLE',
    'VERSION_OBSOLETA',
  ]) {
    testWidgets('$codigo recarga tras elegir predeterminada', (t) async {
      final repo = RepoCuentas()
        ..lista = [cuenta(registro: 'registrado', apta: true)]
        ..errorAccion = CuentasException(
          codigo,
          codigo == 'CUENTA_NO_ENCONTRADA' ? 404 : 409,
          codigo,
        );
      await abrir(t, repo);
      await t.tap(find.text('Elegir por defecto'));
      await t.pumpAndSettle();
      expect(repo.defaults, 1);
      expect(repo.lecturas, 2);
      expect(find.text(codigo), findsOneWidget);
    });
  }
  testWidgets('elegir predeterminada envia version y actualiza', (t) async {
    final repo = RepoCuentas()
      ..lista = [cuenta(registro: 'registrado', apta: true)];
    await abrir(t, repo);
    await t.tap(find.text('Elegir por defecto'));
    await t.pumpAndSettle();
    expect(repo.defaults, 1);
    expect(repo.lecturas, 2);
  });
  testWidgets('sync pronto deshabilita hasta vencer espera', (t) async {
    final repo = RepoCuentas()
      ..lista = [cuenta(registro: 'registrado')]
      ..errorAccion = CuentasException(
        'SYNC_PRONTO',
        429,
        'Espera antes de sincronizar',
        reintento: 2,
      );
    await abrir(t, repo);
    await t.tap(find.text('Sincronizar'));
    await t.pump();
    expect(repo.syncs, 1);
    expect(
      t
          .widget<OutlinedButton>(
            find.widgetWithText(OutlinedButton, 'Sincronizar'),
          )
          .onPressed,
      isNull,
    );
    await t.pump(const Duration(seconds: 3));
    expect(
      t
          .widget<OutlinedButton>(
            find.widgetWithText(OutlinedButton, 'Sincronizar'),
          )
          .onPressed,
      isNotNull,
    );
  });
  for (final codigo in ['ERROR', 'RED']) {
    testWidgets('$codigo permite reintentar sincronizacion', (t) async {
      final repo = RepoCuentas()
        ..lista = [cuenta(registro: 'registrado')]
        ..errorAccion = CuentasException(
          codigo,
          codigo == 'RED' ? null : 503,
          codigo == 'RED' ? 'No pudimos conectar.' : 'Error del servidor',
        );
      await abrir(t, repo);
      await t.tap(find.text('Sincronizar'));
      await t.pumpAndSettle();
      expect(
        find.text(
          codigo == 'RED' ? 'No pudimos conectar.' : 'Error del servidor',
        ),
        findsOneWidget,
      );
      repo.errorAccion = null;
      await t.tap(find.text('Sincronizar'));
      await t.pumpAndSettle();
      expect(repo.syncs, 2);
    });
  }
}
