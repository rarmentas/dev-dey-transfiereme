---
id: 5
type: story
title: "Integración real cobro QR general cero uno"
parent: epic-qr-general
covers: [R1]
after: [1.7, 1.8, 1.9, 3, 4]
hitl: true
risk: high
refined: false
---

# Integración real cobro QR general cero uno

## Description

0.01 tras gates.

## Requirements

Verify: Hitl 0.01.

1. **Bloqueo sin gates** (C2)
   **Given** 1.8 no done
   **When** tickets.py next
   **Then** historia bloqueada

2. **Cobro real** (C2)
   **Given** gates done y adaptador producción
   **When** cliente paga 0.01
   **Then** movimiento Transferencia 0.01

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md

## Notes

- Assumption: aprobación humana pendiente.
- Open question: segundo pago obligatorio para R1 en integración.
