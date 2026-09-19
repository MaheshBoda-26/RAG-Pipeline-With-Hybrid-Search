# Aegis API — Errors and Retries

Reference documentation for the Aegis platform API. Every statement below is normative for the current API version.

## What does the VALIDATION_ERROR error code mean

VALIDATION_ERROR (422): the request body failed schema validation. The details field lists each failing field and why.

## What does the INTERNAL_ERROR error code mean

INTERNAL_ERROR (500): an unexpected server error. These are logged with a request_id -- include it when contacting support.

## Which error codes are safe to retry with exponential backoff

RATE_LIMITED and INTERNAL_ERROR are safe to retry with exponential backoff. VALIDATION_ERROR, PERMISSION_DENIED, and CONFLICT will not succeed on retry without changing the request itself.

## Which error codes will NOT succeed on retry without changing the request

VALIDATION_ERROR, PERMISSION_DENIED, and CONFLICT will not succeed on retry without changing the request itself.

## What HTTP status code does VALIDATION_ERROR return

VALIDATION_ERROR (422): the request body failed schema validation.

## What HTTP status code does CONFLICT return

CONFLICT (409): the operation would violate a uniqueness constraint.

## What HTTP status code does INTERNAL_ERROR return

INTERNAL_ERROR (500): an unexpected server error.

## What should you include when contacting support about an INTERNAL_ERROR

INTERNAL_ERROR (500): an unexpected server error. These are logged with a request_id -- include it when contacting support.

## What should you do if you get a VALIDATION_ERROR

VALIDATION_ERROR (422): the request body failed schema validation. The details field lists each failing field and why. VALIDATION_ERROR, PERMISSION_DENIED, and CONFLICT will not succeed on retry without changing the request itself.
