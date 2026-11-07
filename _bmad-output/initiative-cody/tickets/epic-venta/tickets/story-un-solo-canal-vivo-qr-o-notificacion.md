---
id: 2
type: story
title: "Un solo canal vivo QR o notificación"
parent: epic-venta
covers: [R2, R3]
after: [1]
hitl: false
risk: high
refined: false
---

# Un solo canal vivo QR o notificación

## Description

R3 C12.

## Requirements

Verify: Tests.

1. **Canal bloqueado** (R3)
   **Given** QR pendiente
   **When** elegir notificación
   **Then** rechazado

2. **Venta pendiente** (C12)
   **Given** venta pendiente
   **When** nueva venta
   **Then** rechazado

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md
