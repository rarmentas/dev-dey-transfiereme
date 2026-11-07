# Manifiesto de diseño de historias (worktree)

Documentación de diseño; ver también [MANIFIESTO-HISTORIAS-CINCO-EPICAS.md](MANIFIESTO-HISTORIAS-CINCO-EPICAS.md) para alcance del MR apilado.

## Contrato sin sexta épica

El habilitador transversal son **9 historias de apertura** en `epic-sesion` (`1.1`–`1.9`), no una carpeta ni `[[epic]]` adicional. Las **5 historias de acceso** son `1.10`–`1.14`.

## MR apilado

| Incluir en MR historias | Excluir (primer MR / otro worker) |
|---|---|
| `epic-*/tickets/tickets.toml` + `story-*.md` (5 épicas) | `tickets/tickets.toml` iniciativa (igual a HEAD) |
| | `epic-*/epic-*.md` |
| | `scripts/` generadores |

## Aprobación BMad

- `refined: false` en las 32 historias = criterios redactados, **sin aprobación humana**.
- No declarar listo para construir hasta refine + decisión de producto (`unknown` en **1.8**).
