import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.RAG_API_URL || "http://localhost:8000";

export async function DELETE(req: NextRequest) {
  try {
    const source = req.nextUrl.searchParams.get("source");
    if (!source) {
      return NextResponse.json({ error: "source query parameter is required" }, { status: 400 });
    }

    const upstream = await fetch(
      `${BACKEND_URL}/v1/demo/documents?source=${encodeURIComponent(source)}`,
      {
        method: "DELETE",
        headers: req.headers.get("cookie") ? { Cookie: req.headers.get("cookie") as string } : {},
        cache: "no-store",
      }
    );

    const data = await upstream.json();
    if (!upstream.ok) {
      return NextResponse.json(
        { error: data.detail || data.error || "Delete failed" },
        { status: upstream.status }
      );
    }
    return NextResponse.json(data);
  } catch (err) {
    console.error("RAG API demo documents delete proxy error:", err);
    return NextResponse.json({ error: "Backend RAG API unreachable" }, { status: 502 });
  }
}

export async function GET(req: NextRequest) {
  try {
    // Forward cookies for session management
    const cookieHeader = req.headers.get("cookie");
    const headers: Record<string, string> = {};
    if (cookieHeader) {
      headers["Cookie"] = cookieHeader;
    }

    const upstream = await fetch(`${BACKEND_URL}/v1/demo/documents`, {
      method: "GET",
      headers,
      cache: "no-store",
    });

    const data = await upstream.json();

    if (!upstream.ok) {
      return NextResponse.json(
        { error: data.detail || data.error || "Upstream pipeline error" },
        { status: upstream.status }
      );
    }

    return NextResponse.json(data);
  } catch (err) {
    console.error("RAG API demo documents proxy error:", err);
    return NextResponse.json(
      { error: "Backend RAG API unreachable" },
      { status: 502 }
    );
  }
}