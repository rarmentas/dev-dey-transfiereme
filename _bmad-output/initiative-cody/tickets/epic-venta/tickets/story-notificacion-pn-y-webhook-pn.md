---
id: 3
type: story
title: "Notificacion pn y webhook pn"
parent: epic-venta
covers: [R3, R4]
after: [1.5, 2]
hitl: false
risk: high
refined: false
---

# Notificacion pn y webhook pn

## Description

pn webhook.

## Requirements

Verify: Tests.

1. **Monto pn** (R3)
   **Given** monto 0
   **When** pn
   **Then** rechazo

2. **transactionId único** (R4)
   **Given** aviso duplicado transactionId
   **When** reprocesa
   **Then** un pagado

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md
