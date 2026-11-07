---
id: 2
type: story
title: "Ruta webhook QR con puerto de firma"
parent: epic-qr-general
covers: [R1, R4]
after: [1.5, 1]
hitl: false
risk: high
refined: false
---

# Ruta webhook QR con puerto de firma

## Description

codi.qr.payment_received.

## Requirements

Verify: Fixture webhook.

1. **Primer aviso** (R4)
   **Given** cobro pendiente qr_general
   **When** aviso válido
   **Then** pagado una vez

2. **Comercio del cobro** (R7)
   **Given** aviso para cobro de comercio B
   **When** comercio A tiene sesión separada
   **Then** solo B actualiza

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md
