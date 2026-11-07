---
id: 9
type: story
title: "Gate avisos firmados e idempotencia en URL pública"
parent: epic-sesion
covers: []
after: [8]
hitl: true
risk: high
refined: false
---

# Gate avisos firmados e idempotencia en URL pública

## Description

Webhook real y prueba idempotencia.

## Requirements

Verify: Checklist portal.

1. **URL pública** (C10)
   **Given** WEBHOOK_BASE_URL configurada
   **When** portal pey entrega evento
   **Then** log o entrega exitosa en checklist

2. **Idempotencia real** (R4)
   **Given** reintento pey
   **When** mismo transactionId en prueba controlada
   **Then** un solo movimiento pagado

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md
