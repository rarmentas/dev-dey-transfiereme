---
id: 10
type: story
title: "API de sesión entrar salir estado"
parent: epic-sesion
covers: [R7]
after: [2]
hitl: false
risk: medium
refined: false
---

# API de sesión entrar salir estado

## Description

DRF sesión.

## Requirements

Verify: Tests sesión.

1. **Entrar** (R7)
   **Given** credenciales válidas
   **When** POST entrar
   **Then** sesión creada

2. **Salir** (R7)
   **Given** sesión activa
   **When** POST salir
   **Then** sesión invalidada

## References

- parent — _bmad-output/initiative-cody/initiative-cody.md, Requirements
- architecture — docs/stack-tecnologico/000-stack.md
