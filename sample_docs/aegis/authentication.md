# Aegis API — Authentication

Reference documentation for the Aegis platform API. Every statement below is normative for the current API version.

## What are the two authentication methods supported by the Aegis API

The Aegis API supports two authentication methods: OAuth2 and static API keys. Choose OAuth2 for user-facing applications and API keys for server-to-server integrations.

## How do you authenticate with an API key in the Aegis API

To authenticate with an API key, include it in the Authorization header: Authorization: Bearer aegis_live_xxxxxxxxxxxx

## What happens when you make a request without a valid API key

Requests without a valid key return 401 Unauthorized.

## What happens when a read-only API key attempts a write operation

Requests with a valid but read-only key attempting a write operation return 403 Forbidden.

## What is the OAuth2 authorization endpoint for Aegis

The authorization endpoint is https://auth.aegis.example.com/oauth/authorize and the token endpoint is https://auth.aegis.example.com/oauth/token.

## What is the OAuth2 token endpoint for Aegis

The authorization endpoint is https://auth.aegis.example.com/oauth/authorize and the token endpoint is https://auth.aegis.example.com/oauth/token.

## How long do OAuth2 access tokens last before expiring

Access tokens expire after 1 hour. Use the returned refresh_token to obtain a new access token without requiring the user to log in again.

## How do you get a new OAuth2 access token after it expires

Access tokens expire after 1 hour. Use the returned refresh_token to obtain a new access token without requiring the user to log in again.

## What is the rate limit for authenticated requests per API key

Authenticated requests are limited to 1000 requests per minute per API key, and 100 requests per minute per OAuth2 access token.

## What is the rate limit for OAuth2 access tokens

Authenticated requests are limited to 1000 requests per minute per API key, and 100 requests per minute per OAuth2 access token.

## What does the AUTH_INVALID_KEY error code mean

AUTH_INVALID_KEY (401): the provided API key does not exist or has been revoked.

## What does the AUTH_EXPIRED_TOKEN error code mean

AUTH_EXPIRED_TOKEN (401): the OAuth2 access token has expired. Use the refresh token to obtain a new one.

## What does the PERMISSION_DENIED error code mean

PERMISSION_DENIED (403): the authenticated principal does not have the required scope for this operation.

## What does the RESOURCE_NOT_FOUND error code mean

RESOURCE_NOT_FOUND (404): the requested resource ID does not exist in this workspace.

## What does the CONFLICT error code mean

CONFLICT (409): the operation would violate a uniqueness constraint, e.g. creating a workspace with a name that's already taken.

## What is the default memory request per pod in the Helm chart

resources.requests.memory: default is 512Mi per pod; increase to 1Gi+ for workspaces indexing more than 1M documents.

## When should you increase the memory request per pod beyond the default

resources.requests.memory: default is 512Mi per pod; increase to 1Gi+ for workspaces indexing more than 1M documents.

## Where are API keys generated in the Aegis dashboard

API keys are generated in the dashboard under Settings > API Keys.

## What scopes can an API key have

Each key is scoped to a single workspace and can be restricted to read-only or read-write access.

## Do API keys expire automatically

Keys do not expire automatically, but can be revoked at any time from the dashboard.

## Where do you register an OAuth2 application in the Aegis dashboard

Register your application at Settings > OAuth Apps to receive a client_id and client_secret.

## What information do you receive when registering an OAuth2 application

Register your application at Settings > OAuth Apps to receive a client_id and client_secret.

## What HTTP status code does AUTH_INVALID_KEY return

AUTH_INVALID_KEY (401): the provided API key does not exist or has been revoked.

## What HTTP status code does PERMISSION_DENIED return

PERMISSION_DENIED (403): the authenticated principal does not have the required scope for this operation.

## What HTTP status code does RESOURCE_NOT_FOUND return

RESOURCE_NOT_FOUND (404): the requested resource ID does not exist in this workspace.

## What error code is returned when creating a workspace with a name that already exists

CONFLICT (409): the operation would violate a uniqueness constraint, e.g. creating a workspace with a name that's already taken.

## Can you use the same API key across multiple workspaces

Each key is scoped to a single workspace and can be restricted to read-only or read-write access.
