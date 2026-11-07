---
id: 2
type: story
title: "Comercio y ámbito en el servidor"
parent: epic-sesion
covers: [R7]
after: [1]
hitl: false
risk: high
refined: false
---

# Comercio y ámbito en el servidor

## Description

Comercio por membresía; sin comercio en cuerpo.

## Requirements

Verify: Tests ámbito dos comercios.

1. **Servidor fija comercio** (R7, C5)
   **Given** usuario miembro del comercio A
   **When** llama un endpoint de cobro sin campo comercio
   **Then** opera solo sobre A

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md
