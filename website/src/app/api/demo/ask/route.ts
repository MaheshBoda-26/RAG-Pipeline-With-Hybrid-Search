import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.RAG_API_URL || "http://localhost:8000";

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

  // Sanitize input - limit length and remove potential injection chars
  const sanitizedQuestion = question.slice(0, 2000).replace(/[<>]/g, "");
  const sanitizedSource = source?.slice(0, 500).replace(/[<>]/g, "") || null;

  try {
    // No auth required for demo, but add rate limiting awareness
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout

    const upstreamBody: Record<string, string> = { question: sanitizedQuestion };
    if (sanitizedSource) {
      upstreamBody.source = sanitizedSource;
    }

    const upstream = await fetch(`${BACKEND_URL}/v1/demo/ask`, {
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
    console.error("RAG API demo proxy error:", err);
    return NextResponse.json(
      { error: "Backend RAG API unreachable" },
      { status: 502 }
    );
  }
}