---
id: 4
type: story
title: "Contrato de correlación de avisos"
parent: epic-sesion
covers: [R4]
after: [3]
hitl: false
risk: high
refined: false
---

# Contrato de correlación de avisos

## Description

Correlación ids; comercio del cobro persistido.

## Requirements

Verify: Tests ids y comercio.

1. **codiQrId ajeno** (R4)
   **Given** cobro con peyQrId almacenado
   **When** aviso con otro codiQrId
   **Then** no se marca pagado

2. **transactionId ajeno en pn** (R4)
   **Given** cobro notificación con peyTransactionId
   **When** aviso con otro transactionId
   **Then** no se marca pagado

3. **Comercio por cobro** (R7)
   **Given** webhook público sin sesión
   **When** el aviso trae ids válidos de un cobro del comercio B
   **Then** no crea ni actualiza movimiento del comercio A

4. **Monto abierto QR** (R1)
   **Given** QR general
   **When** aviso amount 0.01
   **Then** movimiento guarda 0.01

## Boundaries

- Must not change: no correlacionar por numRef.

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md
