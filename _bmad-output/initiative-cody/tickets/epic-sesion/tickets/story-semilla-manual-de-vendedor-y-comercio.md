---
id: 14
type: story
title: "Semilla manual de vendedor y comercio"
parent: epic-sesion
covers: []
after: [11, 12]
hitl: true
risk: low
refined: false
---

# Semilla manual de vendedor y comercio

## Description

Semilla dev explícita.

## Requirements

Verify: Hitl semilla.

1. **Semilla dev** (C11)
   **Given** comando hitl ejecutado
   **When** usuario entra
   **Then** comercio correcto y cero movimientos

2. **Semilla no gate ACTIVE** (C13)
   **Given** semilla_active_dev en datos
   **When** se evalúa gate 1.8
   **Then** la semilla sola no satisface el gate

## Boundaries

- Must not change: sin pantalla de registro público.

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md
