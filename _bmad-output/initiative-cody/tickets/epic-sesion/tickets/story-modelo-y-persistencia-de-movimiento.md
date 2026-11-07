---
id: 3
type: story
title: "Modelo y persistencia de movimiento"
parent: epic-sesion
covers: [R6]
after: [2]
hitl: false
risk: high
refined: false
---

# Modelo y persistencia de movimiento

## Description

Movimiento con canal, estados, montos y procedencia `origen_pey` u `origen_desarrollo` según contrato transversal del stack.

## Requirements

Verify: Tests tres canales y transiciones.

1. **Transiciones** (R4)
   **Given** movimiento pagado
   **When** se intenta pendiente o vencido
   **Then** la operación falla

2. **Monto 0.01** (C2)
   **Given** monto 0.01
   **When** se persiste y lee
   **Then** el valor es exactamente 0.01

3. **Aviso tardío sobre vencido** (R4)
   **Given** movimiento en estado vencido
   **When** llega un aviso firmado válido con ids coincidentes
   **Then** el sistema no cambia a pagado hasta que producto decida (ver Notes)

## Boundaries

- Must not change: no invocar pey desde el modelo.

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md, Contrato transversal de movimientos y cobros

## Notes

- Open question: si un aviso llega después de vencido, ¿se acepta pago, se rechaza o se registra aparte? Producto no ha decidido; el builder no elige comportamiento.
