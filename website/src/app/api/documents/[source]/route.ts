import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.RAG_API_URL || "http://localhost:8000";
const API_KEY = process.env.RAG_API_KEY || "your-secure-api-key-here";

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ source: string }> }
) {
  try {
    const { source } = await params;
    if (!source) {
      return NextResponse.json({ error: "source is required" }, { status: 400 });
    }

    const upstream = await fetch(`${BACKEND_URL}/v1/documents/${source}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${API_KEY}`,
      },
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
    console.error("RAG API delete document proxy error:", err);
    return NextResponse.json(
      { error: "Backend RAG API unreachable" },
      { status: 502 }
    );
  }
}