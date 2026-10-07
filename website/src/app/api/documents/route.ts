import { NextRequest, NextResponse } from "next/server";

import { readUpstream } from "@/lib/upstream";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.RAG_API_URL || "http://localhost:8000";

export async function GET(req: NextRequest) {
  try {
    // Require authentication
    const cookieHeader = req.headers.get("cookie");
    if (!cookieHeader) {
      return NextResponse.json({ error: "Authentication required" }, { status: 401 });
    }

    const headers: Record<string, string> = {
      "Cookie": cookieHeader,
    };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    const upstream = await fetch(`${BACKEND_URL}/v1/documents`, {
      method: "GET",
      headers,
      cache: "no-store",
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    const { ok, status, data, error } = await readUpstream(
      upstream,
      "Upstream pipeline error"
    );

    if (!ok) {
      return NextResponse.json({ error }, { status });
    }

    return NextResponse.json(data);
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      return NextResponse.json({ error: "Request timeout" }, { status: 504 });
    }
    console.error("RAG API documents proxy error:", err);
    return NextResponse.json(
      { error: "Backend RAG API unreachable" },
      { status: 502 }
    );
  }
}