---
id: 4
type: story
title: "Integración real ACTIVE y CLABE en pey"
parent: epic-clabe
covers: []
after: [1.7, 1.8, 1.9, 3]
hitl: true
risk: high
refined: false
---

# Integración real ACTIVE y CLABE en pey

## Description

Gates 1.7-1.9.

## Requirements

Verify: Hitl.

1. **Mismos gates que cobro** (C2, C13)
   **Given** sin 1.9
   **When** start integración CLABE
   **Then** bloqueado

2. **ACTIVE real** (C13)
   **Given** gates ok
   **When** consulta producción
   **Then** ACTIVE documentado y QR real habilitado

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md

## Notes

- Assumption: aprobación humana pendiente.
- Constraints C2 C13 en iniciativa; no en covers.
