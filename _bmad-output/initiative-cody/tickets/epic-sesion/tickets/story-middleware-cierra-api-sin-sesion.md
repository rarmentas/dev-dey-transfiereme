---
id: 11
type: story
title: "Middleware cierra API sin sesión"
parent: epic-sesion
covers: [R7]
after: [10]
hitl: false
risk: high
refined: false
---

# Middleware cierra API sin sesión

## Description

403 fuera excepciones.

## Requirements

Verify: Test 403.

1. **API protegida** (R7)
   **Given** sin usuario
   **When** POST bajo /api/cobro/
   **Then** 403

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md
