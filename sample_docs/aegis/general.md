# Aegis API — Overview

Reference documentation for the Aegis platform API. Every statement below is normative for the current API version.

## What are the health check endpoints exposed by the API server

The API server exposes GET /healthz (liveness) and GET /readyz (readiness, checks database connectivity).

## What does a 503 from /readyz indicate

A 503 from /readyz indicates the database connection pool is exhausted or unreachable.

## Does Aegis support zero-downtime upgrades

Aegis supports rolling upgrades between minor versions without downtime.
