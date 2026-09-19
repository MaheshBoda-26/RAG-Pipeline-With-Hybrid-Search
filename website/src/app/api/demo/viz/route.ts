import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.RAG_API_URL || "http://localhost:8000";

/**
 * GET /api/demo/viz — proxy to the pipeline's vector-space map.
 *
 * Returns REAL chunk embeddings projected to 3D coordinates by the backend.
 * The visualization is read-only and derives every point from stored vectors;
 * nothing here invents sample data.
 */
export async function GET(req: NextRequest) {
  try {
    const params = new URLSearchParams();
    const vectors = req.nextUrl.searchParams.get("vectors");
    const maxChunks = req.nextUrl.searchParams.get("max_chunks");
    if (vectors) params.set("vectors", vectors);
    if (maxChunks) params.set("max_chunks", maxChunks);

    const qs = params.toString();
    const upstream = await fetch(
      `${BACKEND_URL}/v1/demo/viz${qs ? `?${qs}` : ""}`,
      { method: "GET", cache: "no-store" }
    );

    const data = await upstream.json();

    if (!upstream.ok) {
      return NextResponse.json(
        { error: data.detail || data.error || "Upstream pipeline error" },
        { status: upstream.status }
      );
    }

    return NextResponse.json(data);
  } catch (err) {
    console.error("RAG API demo viz proxy error:", err);
    return NextResponse.json(
      { error: "Backend RAG API unreachable" },
      { status: 502 }
    );
  }
}
