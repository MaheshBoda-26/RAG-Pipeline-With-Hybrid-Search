import { NextRequest, NextResponse } from "next/server";

import { readUpstream } from "@/lib/upstream";

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

    // Validate file type (accept MIME type OR file extension - browsers often send empty type for .md/.doc)
    const allowedTypes = [
      "application/pdf",
      "text/plain",
      "text/markdown",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "application/msword",
    ];
    const allowedExtensions = [".pdf", ".docx", ".doc", ".txt", ".md"];
    const ext = "." + file.name.toLowerCase().split(".").pop();
    if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(ext)) {
      return NextResponse.json({ error: "Unsupported file type" }, { status: 400 });
    }

    // No auth required for demo, but forward cookie if present
    const cookieHeader = req.headers.get("cookie");

    const upstreamFormData = new FormData();
    upstreamFormData.append("file", file, file.name);

    const headers: Record<string, string> = {};
    if (cookieHeader) {
      headers["Cookie"] = cookieHeader;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000);

    const upstream = await fetch(`${BACKEND_URL}/v1/demo/upload`, {
      method: "POST",
      headers,
      body: upstreamFormData,
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

    // Upload metadata can report the browser filename even when legacy
    // ingestion stored the chunks under a generated name. Resolve the exact
    // source from the index before telling the UI which document to scope to.
    const documentsResponse = await fetch(`${BACKEND_URL}/v1/demo/documents`, {
      method: "GET",
      headers: cookieHeader ? { Cookie: cookieHeader } : {},
      cache: "no-store",
    });
    if (documentsResponse.ok) {
      const corpus = await documentsResponse.json();
      const documents = Array.isArray(corpus.documents) ? corpus.documents : [];
      const requestedNames = [data.source, data.file, data.stored_as].filter(
        (name): name is string => typeof name === "string" && name.length > 0
      );
      const match = documents.find((doc: { source?: string }) =>
        requestedNames.some((name) =>
          doc.source === name || doc.source?.split("/").pop() === name
        )
      );
      if (match?.source) data.source = match.source;
    }

    return NextResponse.json(data);
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      return NextResponse.json({ error: "Request timeout" }, { status: 504 });
    }
    console.error("RAG API demo upload proxy error:", err);
    return NextResponse.json(
      { error: "Backend RAG API unreachable" },
      { status: 502 }
    );
  }
}
