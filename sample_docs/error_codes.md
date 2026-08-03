# Aegis API Error Codes

## Overview

All Aegis API errors return a JSON body with `error_code`, `message`, and
optionally `details`. HTTP status codes follow standard conventions but the
`error_code` field should be used for programmatic handling since it's
more specific than the HTTP status.

## Common Error Codes

- `AUTH_INVALID_KEY` (401): the provided API key does not exist or has been
  revoked.
- `AUTH_EXPIRED_TOKEN` (401): the OAuth2 access token has expired. Use the
  refresh token to obtain a new one.
- `PERMISSION_DENIED` (403): the authenticated principal does not have the
  required scope for this operation.
- `RATE_LIMITED` (429): request quota exceeded. See the `Retry-After` header.
- `VALIDATION_ERROR` (422): the request body failed schema validation. The
  `details` field lists each failing field and why.
- `RESOURCE_NOT_FOUND` (404): the requested resource ID does not exist in
  this workspace.
- `CONFLICT` (409): the operation would violate a uniqueness constraint,
  e.g. creating a workspace with a name that's already taken.
- `INTERNAL_ERROR` (500): an unexpected server error. These are logged with
  a `request_id` -- include it when contacting support.

## Retry Guidance

`RATE_LIMITED` and `INTERNAL_ERROR` are safe to retry with exponential
backoff. `VALIDATION_ERROR`, `PERMISSION_DENIED`, and `CONFLICT` will not
succeed on retry without changing the request itself.
