---
id: 5
type: story
title: "Integración real venta un canal cero uno"
parent: epic-venta
covers: [R2, R3]
after: [1.7, 1.8, 1.9, 4]
hitl: true
risk: high
refined: false
---

# Integración real venta un canal cero uno

## Description

0.01 gates.

## Requirements

Verify: Hitl.

1. **Gates** (C2)
   **Given** sin 1.9
   **When** start
   **Then** bloqueado

2. **Pago** (C2)
   **Given** gates ok
   **When** canal vivo cobrado
   **Then** movimiento 0.01

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md

## Notes

- Assumption: aprobación humana pendiente.
