---
id: 1
type: story
title: "Alta venta valida monto referencia y concepto"
parent: epic-venta
covers: [R2]
after: [1.6]
hitl: false
risk: high
refined: false
---

# Alta venta valida monto referencia y concepto

## Description

Validación R2.

## Requirements

Verify: Tests.

1. **Referencia** (R2)
   **Given** referencia con letras
   **When** guardar
   **Then** no llama adaptador

2. **Concepto vacío** (R2)
   **Given** concepto vacío monto 0.01
   **When** alta
   **Then** concepto enviado Transferencia

3. **Rechazo** (R2)
   **Given** adaptador dev error
   **When** alta
   **Then** sin estado pagado

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md
