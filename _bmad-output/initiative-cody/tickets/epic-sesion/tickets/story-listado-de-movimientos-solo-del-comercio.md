---
id: 12
type: story
title: "Listado de movimientos solo del comercio"
parent: epic-sesion
covers: [R7]
after: [3, 11]
hitl: false
risk: high
refined: false
---

# Listado de movimientos solo del comercio

## Description

GET scoped.

## Requirements

Verify: Test dos comercios.

1. **Aislamiento listado** (R7)
   **Given** movimiento en B
   **When** sesión A lista
   **Then** no aparece

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md
