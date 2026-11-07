# Manifiesto de historias (cinco épicas)

**Base:** GitLab MR !1 — `docs/epicas-paralelas-20261107` (épicas paralelas + contrato transversal en `docs/stack-tecnologico/000-stack.md`).

## Alcance del MR de historias

Solo añade bajo `tickets/epic-*/tickets/` los `tickets.toml` y `story-*.md`. No modifica README, stack, iniciativa ni `tickets/tickets.toml` de la iniciativa.

## Contrato sin sexta épica

| Bloque | Refs | Cantidad |
|---|---|---:|
| Transversal (contrato + gates) | `1.1` – `1.9` en `epic-sesion` | 9 |
| Acceso sesión/aislamiento | `1.10` – `1.14` | 5 |
| QR / venta / tablero / CLABE | | 18 |
| **Total** | | **32** |

El contrato normativo compartido también está en stack § Contrato transversal; las historias `1.1`–`1.9` lo implementan y verifican en código.

## Integración real

Bloqueadores alineados con MR !1 y stack: ACTIVE confirmado por pey, sesión/aislamiento real, webhook firmado e idempotente. Gates **1.7**–**1.9** son hitl de documentación; adaptador desarrollo no autoriza cobro en producción.

## BMad

`refined: false` en todas; sin aprobación de criterios ni start de build.
