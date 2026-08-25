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

  const { question } = body as { question?: string };
  if (!question || typeof question !== "string" || question.trim() === "") {
    return NextResponse.json({ error: "question is required" }, { status: 400 });
  }

  // Sanitize input - limit length and remove potential injection chars
  const sanitizedQuestion = question.slice(0, 2000).replace(/[<>]/g, "");

  try {
    // Forward cookies for session management (no API key fallback)
    const cookieHeader = req.headers.get("cookie");
    if (!cookieHeader) {
      return NextResponse.json({ error: "Authentication required" }, { status: 401 });
    }

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "Cookie": cookieHeader,
    };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout

    const upstream = await fetch(`${BACKEND_URL}/v1/ask`, {
      method: "POST",
      headers,
      body: JSON.stringify({ question: sanitizedQuestion }),
      cache: "no-store",
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    const data = await upstream.json();

    if (!upstream.ok) {
      // Don't leak internal error details
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
    console.error("RAG API proxy error:", err);
    return NextResponse.json(
      { error: "Backend RAG API unreachable" },
      { status: 502 }
    );
  }
}