# Aegis Platform Deployment Guide

## Supported Environments

Aegis can be deployed on Kubernetes (recommended for production), Docker
Compose (recommended for staging/local), or as a managed service via
Aegis Cloud.

## Kubernetes Deployment

The Helm chart is published at `charts.aegis.example.com/aegis-platform`.
Minimum requirements are Kubernetes 1.27+ and a PostgreSQL 14+ instance
reachable from the cluster.

Key configuration values in `values.yaml`:

- `replicaCount`: number of API server pods. Default is 3.
- `postgres.host` / `postgres.port`: external database connection.
- `resources.requests.memory`: default is 512Mi per pod; increase to 1Gi+
  for workspaces indexing more than 1M documents.
- `ingress.tlsSecretName`: required if `ingress.enabled` is true.

Run `helm upgrade --install aegis aegis/aegis-platform -f values.yaml` to
deploy or update.

## Docker Compose

For local or staging use, `docker-compose.yml` bundles the API server,
worker, and a bundled PostgreSQL instance. Bring it up with
`docker compose up -d`. This configuration is not recommended for
production because the bundled PostgreSQL has no automated backups.

## Health Checks

The API server exposes `GET /healthz` (liveness) and `GET /readyz`
(readiness, checks database connectivity). Configure your orchestrator's
health checks against these endpoints; a 503 from `/readyz` indicates the
database connection pool is exhausted or unreachable.

## Zero-Downtime Upgrades

Aegis supports rolling upgrades between minor versions without downtime.
Major version upgrades require running the migration tool
(`aegis-migrate`) before deploying the new version, and may require brief
read-only downtime depending on the size of the schema change -- check the
release notes for the specific version you're upgrading to.
