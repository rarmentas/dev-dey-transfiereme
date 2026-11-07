---
id: 6
type: story
title: "Puerto pey y cuenta ACTIVE con adaptador desarrollo"
parent: epic-sesion
covers: []
after: [5]
hitl: false
risk: medium
refined: false
---

# Puerto pey y cuenta ACTIVE con adaptador desarrollo

## Description

Adaptador dev sin red; producción no usa semilla.

## Requirements

Verify: Tests sin HTTP en dev.

1. **Dev sin red** (C2)
   **Given** adaptador desarrollo
   **When** tests de integración local
   **Then** no hay HTTP a api.pey.mx

2. **Producción ignora semilla** (C13)
   **Given** comercio con semilla_active_dev=true en base
   **When** adaptador producción consulta ACTIVE
   **Then** solo codiStatus de pey decide; la semilla no equivale a ACTIVE

## Boundaries

- Must not change: PEY_API_KEY no en frontend.

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md
