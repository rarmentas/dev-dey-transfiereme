import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

/// Marco con la navegación inferior: Inicio, Movimientos, Tablero, Ajustes.
class TfShell extends StatelessWidget {
  const TfShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: navigationShell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: navigationShell.currentIndex,
        onDestinationSelected: (indice) => navigationShell.goBranch(
          indice,
          initialLocation: indice == navigationShell.currentIndex,
        ),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home_rounded),
            label: 'Inicio',
          ),
          NavigationDestination(
            icon: Icon(Icons.format_list_bulleted_rounded),
            label: 'Movimientos',
          ),
          NavigationDestination(
            icon: Icon(Icons.bar_chart_rounded),
            label: 'Tablero',
          ),
          NavigationDestination(
            icon: Icon(Icons.tune_rounded),
            label: 'Ajustes',
          ),
        ],
      ),
    );
  }
}
