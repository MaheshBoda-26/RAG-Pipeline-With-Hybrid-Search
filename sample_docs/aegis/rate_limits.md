# Aegis API — Rate Limits and Quotas

Reference documentation for the Aegis platform API. Every statement below is normative for the current API version.

## What headers indicate rate limit status

The current limit and remaining quota are returned in the X-RateLimit-Limit and X-RateLimit-Remaining response headers.

## What happens when you exceed the rate limit

Exceeding the limit returns 429 Too Many Requests with a Retry-After header indicating how many seconds to wait.

## What does the RATE_LIMITED error code mean and how should you handle it

RATE_LIMITED (429): request quota exceeded. See the Retry-After header. RATE_LIMITED and INTERNAL_ERROR are safe to retry with exponential backoff.

## What HTTP status code does RATE_LIMITED return

RATE_LIMITED (429): request quota exceeded.

## How do you know what your current rate limit quota is

The current limit and remaining quota are returned in the X-RateLimit-Limit and X-RateLimit-Remaining response headers.
