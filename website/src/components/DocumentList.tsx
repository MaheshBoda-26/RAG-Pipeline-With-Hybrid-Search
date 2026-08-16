"use client";

import * as React from "react";
import { FileText, Trash2, Loader2, AlertCircle, CheckCircle, X } from "lucide-react";

interface Document {
  source: string;
  chunk_count: number;
  created?: string;
}

interface DocumentListProps {
  onDocumentDeleted?: () => void;
}

export function DocumentList({ onDocumentDeleted }: DocumentListProps) {
  const [documents, setDocuments] = React.useState<Document[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [deleting, setDeleting] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = React.useState<string | null>(null);

  const fetchDocuments = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/documents", {
        method: "GET",
        cache: "no-store",
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || data.detail || "Failed to fetch documents");
      }
      setDocuments(data.documents || []);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  React.useEffect(() => {
    fetchDocuments();
  }, []);

  const handleDelete = async (source: string) => {
    setDeleteConfirm(source);
  };

  const confirmDelete = async (source: string) => {
    setDeleting(source);
    setDeleteConfirm(null);
    try {
      const res = await fetch(`/api/documents/${encodeURIComponent(source)}`, {
        method: "DELETE",
        cache: "no-store",
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || data.detail || "Failed to delete document");
      }
      setDocuments(prev => prev.filter(d => d.source !== source));
      onDocumentDeleted?.();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setDeleting(null);
    }
  };

  const cancelDelete = () => {
    setDeleteConfirm(null);
  };

  const formatSize = (chunks: number) => `${chunks} chunk${chunks !== 1 ? "s" : ""}`;

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return "Unknown date";
    try {
      return new Date(dateStr).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  if (loading) {
    return (
      <div className="bg-surface border border-border rounded-xl p-8 text-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-4" />
        <p className="text-muted-foreground">Loading documents...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-surface border border-border rounded-xl p-6">
        <div className="flex items-center gap-3 text-destructive">
          <AlertCircle className="w-6 h-6" />
          <p>Failed to load documents: {error}</p>
        </div>
        <button
          onClick={fetchDocuments}
          className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary-hover transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FileText className="w-6 h-6 text-primary" />
          <h3 className="text-xl font-semibold">Your Documents</h3>
        </div>
        <span className="text-sm text-muted-foreground">
          {documents.length} document{documents.length !== 1 ? "s" : ""}
        </span>
      </div>

      {documents.length === 0 ? (
        <div className="p-12 text-center">
          <FileText className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
          <p className="text-muted-foreground text-lg">No documents uploaded yet</p>
          <p className="text-sm text-muted-foreground/70 mt-1">Upload documents using the uploader above to get started</p>
        </div>
      ) : (
        <div className="divide-y divide-border">
          {documents.map((doc) => (
            <div
              key={doc.source}
              className="px-6 py-4 flex items-center justify-between hover:bg-surface/50 transition-colors"
            >
              <div className="flex items-center gap-4 min-w-0 flex-1">
                <FileText className="w-8 h-8 text-muted-foreground flex-shrink-0" />
                <div className="min-w-0">
                  <p className="font-medium truncate">{doc.source}</p>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground mt-1">
                    <span>{formatSize(doc.chunk_count)}</span>
                    {doc.created && <span>{formatDate(doc.created)}</span>}
                  </div>
                </div>
              </div>

              {deleteConfirm === doc.source ? (
                <div className="flex items-center gap-2 ml-4">
                  <p className="text-sm text-muted-foreground">Delete?</p>
                  <button
                    onClick={() => confirmDelete(doc.source)}
                    disabled={deleting === doc.source}
                    className="px-3 py-1.5 bg-destructive text-destructive-foreground rounded-lg text-sm font-medium hover:bg-destructive/90 disabled:opacity-50 transition-colors flex items-center gap-1"
                  >
                    {deleting === doc.source ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <CheckCircle className="w-4 h-4" />
                    )}
                  </button>
                  <button
                    onClick={cancelDelete}
                    className="px-3 py-1.5 bg-muted text-muted-foreground rounded-lg text-sm font-medium hover:bg-muted/80 transition-colors flex items-center gap-1"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => handleDelete(doc.source)}
                  disabled={deleting === doc.source}
                  className="text-muted-foreground hover:text-destructive transition-colors p-2 ml-4 rounded-lg hover:bg-destructive/10 disabled:opacity-50"
                  aria-label={`Delete ${doc.source}`}
                >
                  <Trash2 className="w-5 h-5" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}