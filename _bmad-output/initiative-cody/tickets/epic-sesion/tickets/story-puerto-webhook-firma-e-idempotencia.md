---
id: 5
type: story
title: "Puerto webhook firma e idempotencia"
parent: epic-sesion
covers: [R4]
after: [4]
hitl: false
risk: high
refined: false
---

# Puerto webhook firma e idempotencia

## Description

Firma cuerpo crudo; idempotencia webhook-id y transactionId.

## Requirements

Verify: Tests firma y duplicados.

1. **Firma inválida** (C7)
   **Given** headers sin firma válida
   **When** el puerto verifica cuerpo crudo
   **Then** rechaza sin movimiento pagado

2. **Clave webhook-id** (C7)
   **Given** stack fija idempotencia por webhook-id
   **When** llega aviso repetido con mismo webhook-id
   **Then** no se aplica dos veces el monto

4. **Mismo transactionId** (R4, diseño)
   **Given** transactionId ya marcó pagado
   **When** llega nuevo webhook-id con mismo transactionId
   **Then** no crea segundo movimiento (refuerzo además de webhook-id)

## Boundaries

- Must not change: persistencia pagado en misma transacción DB.

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md
