/**
 * Shared helpers for proxying responses from the RAG API backend.
 *
 * The backend can fail with a non-JSON body (uvicorn's plain-text
 * "Internal Server Error", a proxy HTML error page, or a truncated response).
 * Calling `response.json()` directly on those throws a SyntaxError, which the
 * route catch-all then reports as "Backend RAG API unreachable" — masking the
 * real upstream failure. Always read the body through `readUpstream` instead.
 */

export type UpstreamResult = {
  ok: boolean;
  status: number;
  data: Record<string, unknown>;
  /** Human-readable message suitable for surfacing in the UI. */
  error: string | null;
};

const MAX_ERROR_LENGTH = 500;

function normalizeText(text: string): string {
  const collapsed = text.replace(/\s+/g, " ").trim();
  return collapsed.length > MAX_ERROR_LENGTH
    ? `${collapsed.slice(0, MAX_ERROR_LENGTH)}…`
    : collapsed;
}

/**
 * Read an upstream Response into a JSON object plus a usable error message.
 * Never throws on a malformed body.
 */
export async function readUpstream(
  response: Response,
  fallbackError: string
): Promise<UpstreamResult> {
  let body: unknown = {};
  try {
    const raw = await response.text();
    if (raw) {
      try {
        body = JSON.parse(raw);
      } catch {
        body = { detail: normalizeText(raw) };
      }
    }
  } catch {
    body = {};
  }

  const data =
    body && typeof body === "object" && !Array.isArray(body)
      ? (body as Record<string, unknown>)
      : { detail: typeof body === "string" ? normalizeText(body) : undefined };

  const detail = data.detail ?? data.error ?? data.message;
  const error = response.ok
    ? null
    : typeof detail === "string" && detail.trim()
      ? detail
      : fallbackError;

  return { ok: response.ok, status: response.status, data, error };
}