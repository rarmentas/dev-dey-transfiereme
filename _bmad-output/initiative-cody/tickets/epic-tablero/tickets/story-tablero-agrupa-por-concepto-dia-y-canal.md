---
id: 2
type: story
title: "Tablero agrupa por concepto día y canal"
parent: epic-tablero
covers: [R6]
after: [1]
hitl: false
risk: medium
refined: false
---

# Tablero agrupa por concepto día y canal

## Description

Agrupación.

## Requirements

Verify: Tests.

1. **Normalización** (R6)
   **Given** Transferencia y transferencia
   **When** agrupa
   **Then** un concepto

2. **Canal** (R6)
   **Given** mismos concepto y día canales distintos
   **When** agrupa
   **Then** filas separadas

3. **Zona horaria** (C6)
   **Given** 23:30 America/Mexico_City
   **When** asigna día
   **Then** día local México

4. **Origen y dinero real** (R6)
   **Given** totales del tablero en vista cobro confirmado
   **When** hay filas origen_desarrollo
   **Then** no se suman en totales que representen cobro confirmado por pey

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md
