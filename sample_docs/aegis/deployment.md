# Aegis API — Deployment and Environments

Reference documentation for the Aegis platform API. Every statement below is normative for the current API version.

## What are the supported deployment environments for Aegis

Aegis can be deployed on Kubernetes (recommended for production), Docker Compose (recommended for staging/local), or as a managed service via Aegis Cloud.

## Where is the Helm chart for Aegis Kubernetes deployment published

The Helm chart is published at charts.aegis.example.com/aegis-platform.

## What are the minimum Kubernetes and PostgreSQL versions for Aegis deployment

Minimum requirements are Kubernetes 1.27+ and a PostgreSQL 14+ instance reachable from the cluster.

## What is the default replica count for API server pods in the Helm chart

replicaCount: number of API server pods. Default is 3.

## What is required if ingress is enabled in the Helm chart

ingress.tlsSecretName: required if ingress.enabled is true.

## How do you deploy or update Aegis using Helm

Run helm upgrade --install aegis aegis/aegis-platform -f values.yaml to deploy or update.

## What services are included in the Docker Compose setup

For local or staging use, docker-compose.yml bundles the API server, worker, and a bundled PostgreSQL instance.

## Why is Docker Compose not recommended for production

This configuration is not recommended for production because the bundled PostgreSQL has no automated backups.

## What is required for major version upgrades

Major version upgrades require running the migration tool (aegis-migrate) before deploying the new version, and may require brief read-only downtime depending on the size of the schema change.

## What is the Aegis Cloud deployment option

Aegis can be deployed on Kubernetes (recommended for production), Docker Compose (recommended for staging/local), or as a managed service via Aegis Cloud.
