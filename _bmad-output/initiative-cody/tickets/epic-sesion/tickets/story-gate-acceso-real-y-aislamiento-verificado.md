---
id: 7
type: story
title: "Gate acceso real y aislamiento verificado"
parent: epic-sesion
covers: [R7]
after: [6]
hitl: true
risk: high
refined: false
---

# Gate acceso real y aislamiento verificado

## Description

Checklist manual sesión y aislamiento.

## Requirements

Verify: Checklist firmado.

1. **Sin sesión** (R7)
   **Given** sin cookie
   **When** GET movimientos
   **Then** 403

2. **Otro comercio** (R7)
   **Given** sesión comercio A
   **When** busca movimiento de B
   **Then** 404

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md
