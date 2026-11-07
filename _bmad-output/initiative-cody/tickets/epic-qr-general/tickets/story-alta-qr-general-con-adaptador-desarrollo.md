---
id: 1
type: story
title: "Alta QR general con adaptador desarrollo"
parent: epic-qr-general
covers: [R1]
after: [1.6]
hitl: false
risk: high
refined: false
---

# Alta QR general con adaptador desarrollo

## Description

QR amount 0 sin expiración en dev.

## Requirements

Verify: Test dev ACTIVE simulado.

1. **ACTIVE simulado** (R1)
   **Given** adaptador dev ACTIVE
   **When** alta QR general
   **Then** qrString persistido

2. **Inactivo** (C13)
   **Given** PENDING en dev
   **When** alta
   **Then** error sin pagado

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md
