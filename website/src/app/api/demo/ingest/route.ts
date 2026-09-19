import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.RAG_API_URL || "http://localhost:8000";

/**
 * POST /api/demo/ingest — proxy to the demo sample-corpus ingest endpoint.
 *
 * Idempotent on the backend (incremental ingest skips unchanged documents),
 * so the "Ingest Sample Docs" button is safe to click repeatedly.
 */
export async function POST(_req: NextRequest) {
  try {
    const upstream = await fetch(`${BACKEND_URL}/v1/demo/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    });

    const data = await upstream.json();

    if (!upstream.ok) {
      return NextResponse.json(
        { error: data.detail || data.error || "Upstream ingest failed" },
        { status: upstream.status }
      );
    }

    return NextResponse.json(data);
  } catch (err) {
    console.error("RAG API demo ingest proxy error:", err);
    return NextResponse.json(
      { error: "Backend RAG API unreachable" },
      { status: 502 }
    );
  }
}
