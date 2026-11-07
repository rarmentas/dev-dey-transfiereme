---
id: 8
type: story
title: "Gate cuenta ACTIVE real en pey"
parent: epic-sesion
covers: []
after: [7]
hitl: true
risk: high
refined: false
---

# Gate cuenta ACTIVE real en pey

## Description

ACTIVE real; semilla dev invalida para este gate.

## Requirements

Verify: Evidencia en notas.

1. **ACTIVE en pey** (C2, C13)
   **Given** CLABE del vendedor demo
   **When** persona consulta pey o portal
   **Then** codiStatus ACTIVE queda documentado en notas sin API key en cliente

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md

## Notes

- Unknown: CLABE Banxico 012180015826225713 vs cuenta propia — bloquea integraciones que dependan de 1.8.
