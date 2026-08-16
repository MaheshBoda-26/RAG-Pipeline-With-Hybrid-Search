import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.RAG_API_URL || "http://localhost:8000";
const API_KEY = process.env.RAG_API_KEY || "your-secure-api-key-here";

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const file = formData.get("file") as File;

    if (!file) {
      return NextResponse.json({ error: "file is required" }, { status: 400 });
    }

    // Forward to backend with cookies for authenticated users
    const upstreamFormData = new FormData();
    upstreamFormData.append("file", file, file.name);

    // Forward cookies for session management
    const cookieHeader = req.headers.get("cookie");
    const headers: Record<string, string> = {};
    if (cookieHeader) {
      headers["Cookie"] = cookieHeader;
    } else {
      // Fallback to API key for backward compatibility
      headers["Authorization"] = `Bearer ${API_KEY}`;
    }

    const upstream = await fetch(`${BACKEND_URL}/v1/upload`, {
      method: "POST",
      headers,
      body: upstreamFormData,
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
    console.error("RAG API upload proxy error:", err);
    return NextResponse.json(
      { error: "Backend RAG API unreachable" },
      { status: 502 }
    );
  }
}