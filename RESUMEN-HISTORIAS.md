# RESUMEN-HISTORIAS

Historias BMad apiladas sobre **MR !1** (`origin/docs/epicas-paralelas-20261107`). Worktree `historias-20261107`. **No listo para construir.**

## Base intacta (MR !1)

Conservados sin modificación respecto a `origin/docs/epicas-paralelas-20261107`:

- `README.md`
- `docs/stack-tecnologico/000-stack.md` (incl. **Contrato transversal de movimientos y cobros**)
- `_bmad-output/initiative-cody/initiative-cody.md`
- `_bmad-output/initiative-cody/tickets/tickets.toml` (5 épicas, **sin `after` entre épicas**, sin sexta épica)

## Conteo

| Épica | Historias | Notas |
|---|---:|---|
| `epic-sesion` | 14 | **9** transversales (`1.1`–`1.9`) + **5** acceso (`1.10`–`1.14`) |
| `epic-qr-general` | 5 | |
| `epic-venta` | 5 | |
| `epic-tablero` | 4 | |
| `epic-clabe` | 4 | |
| **Total** | **32** | |

Contrato transversal = historias de apertura en sesión + contrato documental en stack; **no** épica ni carpeta aparte.

## Metodología de validación

| Herramienta | Uso en esta rama |
|---|---|
| `tickets.py` | **No ejecutado** (permiso denegado en entorno; no reintentar ni sortear). |
| Comprobación previa (pre-corrección) | Árbol temporal `/tmp/codi-historias-val-20261107` con envelopes mínimos: 32 entradas, 0 drift — **obsoleto** tras alinear a MR !1; no repetir sin `tickets.py`. |
| Validación actual | Script local **solo TOML/markdown** (`/tmp/codi-validate-toml-only.py`): conteos, refs `1.n` / hermanos, sin `after` a épica entera, iniciativa sin `after` inter-épica, 0× `refined: true`. |

**Última corrida TOML-only (2026-11-07):** `total 32`, `cross_refs_ok True`.

## Estado BMad

- Todas las historias: `refined: false`; criterios **redactados** (Given/When/Then); **aprobación humana pendiente**.
- `unknown` en entrada **1.8** (CLABE) — integraciones **2.5**, **3.5**, **5.4** diseñadas con `after` gates **1.7–1.9** pero bloqueo producto no automatizado sin `tickets.py`.

## Alineación MR !1

- Paralelismo de épicas: sin dependencias `after` en `tickets.toml` de iniciativa.
- Historias usan prerrequisitos **granulares** (`1.3`, `1.5`, `1.6`, `1.7`–`1.9`), no cierre de épica completa.
- Modelo/tablero citan `origen_pey` / `origen_desarrollo` del stack.

## Archivos propios del MR historias

```
_bmad-output/initiative-cody/tickets/epic-*/tickets/tickets.toml
_bmad-output/initiative-cody/tickets/epic-*/tickets/story-*.md
MANIFIESTO-HISTORIAS-CINCO-EPICAS.md
MANIFIESTO-DISENO-HISTORIAS.md
RESUMEN-HISTORIAS.md
```

No incluir: `epic-*/epic-*.md` (vendrán del corte de épicas si aplica), scripts helper, `tickets.toml` de iniciativa.

## Decisiones pendientes

1. CLABE Banxico vs propia (`unknown` **1.8**).
2. Aviso tras `vencido` (Open question **1.3**).
3. Segundo $0.01 QR para R1 en integración (notas **2.5**).
