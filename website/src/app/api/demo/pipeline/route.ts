import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.RAG_API_URL || "http://localhost:8000";

/**
 * POST /api/demo/pipeline — proxy to the pipeline-trace endpoint.
 *
 * The backend runs one REAL ask() and returns the answer plus per-stage
 * timings, retrieval lanes and the confidence breakdown. The pipeline console
 * renders exactly what the API returns — no client-side simulation.
 */
export async function POST(req: NextRequest) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const { question, source } = body as { question?: string; source?: string };
  if (!question || typeof question !== "string" || question.trim() === "") {
    return NextResponse.json({ error: "question is required" }, { status: 400 });
  }

  // Same sanitization policy as the ask proxy.
  const sanitizedQuestion = question.slice(0, 2000).replace(/[<>]/g, "");
  const sanitizedSource = source?.slice(0, 500).replace(/[<>]/g, "") || null;

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 120000);

    const upstreamBody: Record<string, string> = { question: sanitizedQuestion };
    if (sanitizedSource) {
      upstreamBody.source = sanitizedSource;
    }

    const upstream = await fetch(`${BACKEND_URL}/v1/demo/pipeline`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(upstreamBody),
      cache: "no-store",
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    const data = await upstream.json();

    if (!upstream.ok) {
      return NextResponse.json(
        { error: "Upstream pipeline error" },
        { status: upstream.status }
      );
    }

    return NextResponse.json(data);
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      return NextResponse.json({ error: "Request timeout" }, { status: 504 });
    }
    console.error("RAG API pipeline trace proxy error:", err);
    return NextResponse.json(
      { error: "Backend RAG API unreachable" },
      { status: 502 }
    );
  }
}
