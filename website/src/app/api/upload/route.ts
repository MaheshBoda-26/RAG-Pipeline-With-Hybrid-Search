import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.RAG_API_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const file = formData.get("file") as File;

    if (!file) {
      return NextResponse.json({ error: "file is required" }, { status: 400 });
    }

    // Validate file size (10MB max)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      return NextResponse.json({ error: "File too large. Maximum size: 10MB" }, { status: 413 });
    }

    // Validate file type
    const allowedTypes = [
      "application/pdf",
      "text/plain",
      "text/markdown",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "application/msword",
    ];
    if (!allowedTypes.includes(file.type)) {
      return NextResponse.json({ error: "Unsupported file type" }, { status: 400 });
    }

    // Require authentication
    const cookieHeader = req.headers.get("cookie");
    if (!cookieHeader) {
      return NextResponse.json({ error: "Authentication required" }, { status: 401 });
    }

    const upstreamFormData = new FormData();
    upstreamFormData.append("file", file, file.name);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000); // 60s timeout for uploads

    const upstream = await fetch(`${BACKEND_URL}/v1/upload`, {
      method: "POST",
      headers: { "Cookie": cookieHeader },
      body: upstreamFormData,
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
    console.error("RAG API upload proxy error:", err);
    return NextResponse.json(
      { error: "Backend RAG API unreachable" },
      { status: 502 }
    );
  }
}