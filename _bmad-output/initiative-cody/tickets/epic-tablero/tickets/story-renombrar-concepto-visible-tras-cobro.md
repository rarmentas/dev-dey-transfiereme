---
id: 3
type: story
title: "Renombrar concepto visible tras cobro"
parent: epic-tablero
covers: [R5]
after: [2]
hitl: false
risk: medium
refined: false
---

# Renombrar concepto visible tras cobro

## Description

R5.

## Requirements

Verify: Test.

1. **Inmutable enviado** (R5)
   **Given** pagado concepto_enviado Transferencia
   **When** PATCH visible Tortas
   **Then** tablero Tortas y enviado Transferencia

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md
