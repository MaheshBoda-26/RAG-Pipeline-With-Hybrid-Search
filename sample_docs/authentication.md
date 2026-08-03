# Aegis API Authentication

## Overview

The Aegis API supports two authentication methods: OAuth2 and static API keys.
Choose OAuth2 for user-facing applications and API keys for server-to-server
integrations.

## API Keys

API keys are generated in the dashboard under Settings > API Keys. Each key
is scoped to a single workspace and can be restricted to read-only or
read-write access. Keys do not expire automatically, but can be revoked at
any time from the dashboard.

To authenticate with an API key, include it in the `Authorization` header:

```
Authorization: Bearer aegis_live_xxxxxxxxxxxx
```

Requests without a valid key return `401 Unauthorized`. Requests with a
valid but read-only key attempting a write operation return `403 Forbidden`.

## OAuth2

Aegis implements the standard OAuth2 authorization code flow. Register your
application at Settings > OAuth Apps to receive a `client_id` and
`client_secret`. The authorization endpoint is
`https://auth.aegis.example.com/oauth/authorize` and the token endpoint is
`https://auth.aegis.example.com/oauth/token`.

Access tokens expire after 1 hour. Use the returned `refresh_token` to obtain
a new access token without requiring the user to log in again.

## Rate Limits

Authenticated requests are limited to 1000 requests per minute per API key,
and 100 requests per minute per OAuth2 access token. The current limit and
remaining quota are returned in the `X-RateLimit-Limit` and
`X-RateLimit-Remaining` response headers. Exceeding the limit returns
`429 Too Many Requests` with a `Retry-After` header indicating how many
seconds to wait.
