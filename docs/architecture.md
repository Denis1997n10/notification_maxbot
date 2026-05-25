# Architecture

Hexagonal/layered architecture: Domain -> Application -> Infrastructure -> Interfaces.
Domain/Application must not import infrastructure.
Handlers are thin adapters only.
All new changes go through PR + CI.
