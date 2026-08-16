"use client";

import * as React from "react";
import { Upload, X, CheckCircle, AlertCircle, Loader2, FileText } from "lucide-react";

const ALLOWED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/msword",
  "text/plain",
  "text/markdown",
];

const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".doc", ".txt", ".md"];

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

interface UploadedFile {
  id: string;
  name: string;
  size: number;
  status: "pending" | "uploading" | "success" | "error";
  progress: number;
  error?: string;
}

export function DocumentUploader() {
  const [files, setFiles] = React.useState<UploadedFile[]>([]);
  const [dragActive, setDragActive] = React.useState(false);
  const [isUploading, setIsUploading] = React.useState(false);

  const validateFile = (file: File): string | null => {
    if (!ALLOWED_TYPES.includes(file.type) && !ALLOWED_EXTENSIONS.some(ext => file.name.toLowerCase().endsWith(ext))) {
      return `Unsupported file type. Allowed: PDF, DOCX, DOC, TXT, MD`;
    }
    if (file.size > MAX_FILE_SIZE) {
      return `File too large. Maximum size: 10MB`;
    }
    return null;
  };

  const addFiles = (newFiles: FileList | File[]) => {
    const fileArray = Array.from(newFiles);
    const validFiles = fileArray.map(file => {
      const error = validateFile(file);
      return {
        id: `${file.name}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
        name: file.name,
        size: file.size,
        status: error ? "error" : "pending" as const,
        progress: 0,
        error,
      };
    });
    setFiles(prev => [...prev, ...validFiles]);
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(e.target.files);
      e.target.value = "";
    }
  };

  const removeFile = (id: string) => {
    setFiles(prev => prev.filter(f => f.id !== id));
  };

  const uploadFile = async (file: UploadedFile, fileData: File) => {
    setFiles(prev => prev.map(f => f.id === file.id ? { ...f, status: "uploading", progress: 0 } : f));

    try {
      const formData = new FormData();
      formData.append("file", fileData);

      const res = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || data.detail || "Upload failed");
      }

      setFiles(prev => prev.map(f => f.id === file.id ? { ...f, status: "success", progress: 100 } : f));
      return data;
    } catch (err) {
      setFiles(prev => prev.map(f => f.id === file.id ? { ...f, status: "error", error: (err as Error).message } : f));
      return null;
    }
  };

  const handleUploadAll = async () => {
    const pendingFiles = files.filter(f => f.status === "pending");
    if (pendingFiles.length === 0) return;

    setIsUploading(true);
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;

    // We need to match files with their File objects - store them in state
    // For simplicity, we'll re-read from the input if needed, but here we use a different approach
    // Since we can't easily access File objects after initial selection, we'll use a ref
    // Let's use a more practical approach - store the File objects in state
  };

  // Use a ref to store File objects for upload
  const fileRefs = React.useRef<Map<string, File>>(new Map());

  const handleFileSelectWithRef = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const fileArray = Array.from(e.target.files);
      fileArray.forEach(file => {
        const error = validateFile(file);
        const id = `${file.name}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
        fileRefs.current.set(id, file);
        setFiles(prev => [...prev, {
          id,
          name: file.name,
          size: file.size,
          status: error ? "error" : "pending",
          progress: 0,
          error,
        }]);
      });
      e.target.value = "";
    }
  };

  const handleDropWithRef = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const fileArray = Array.from(e.dataTransfer.files);
      fileArray.forEach(file => {
        const error = validateFile(file);
        const id = `${file.name}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
        fileRefs.current.set(id, file);
        setFiles(prev => [...prev, {
          id,
          name: file.name,
          size: file.size,
          status: error ? "error" : "pending",
          progress: 0,
          error,
        }]);
      });
    }
  };

  const uploadAll = async () => {
    const pendingFiles = files.filter(f => f.status === "pending");
    if (pendingFiles.length === 0) return;

    setIsUploading(true);

    for (const file of pendingFiles) {
      const fileData = fileRefs.current.get(file.id);
      if (fileData) {
        await uploadFile(file, fileData);
      }
    }

    setIsUploading(false);
  };

  const clearCompleted = () => {
    setFiles(prev => {
      const toRemove = prev.filter(f => f.status === "success");
      toRemove.forEach(f => fileRefs.current.delete(f.id));
      return prev.filter(f => f.status !== "success");
    });
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const hasErrors = files.some(f => f.status === "error");
  const hasPending = files.some(f => f.status === "pending");
  const allSuccess = files.length > 0 && files.every(f => f.status === "success");

  return (
    <div className="bg-surface border border-border rounded-xl p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Upload className="w-6 h-6 text-primary" />
        <h3 className="text-xl font-semibold">Upload Documents</h3>
      </div>
      <p className="text-muted-foreground text-sm">
        Drag and drop or click to upload PDF, DOCX, DOC, TXT, or MD files (max 10MB each)
      </p>

      {/* Drop Zone */}
      <div
        className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all ${
          dragActive
            ? "border-primary bg-primary/5"
            : "border-border hover:border-primary/50"
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDropWithRef}
      >
        <input
          type="file"
          id="file-upload"
          multiple
          accept=".pdf,.docx,.doc,.txt,.md"
          onChange={handleFileSelectWithRef}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          aria-label="Upload documents"
        />
        <label htmlFor="file-upload" className="cursor-pointer">
          <Upload className="w-12 h-12 mx-auto text-muted-foreground/50 mb-4" />
          <p className="text-lg font-medium text-foreground mb-1">
            {dragActive ? "Drop files here" : "Drag & drop files here, or click to browse"}
          </p>
          <p className="text-sm text-muted-foreground">
            PDF, DOCX, DOC, TXT, MD &nbsp;•&nbsp; Max 10MB per file
          </p>
        </label>
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {files.map((file) => (
            <div
              key={file.id}
              className={`flex items-center gap-4 p-4 bg-surface/50 border rounded-lg transition-all ${
                file.status === "success" ? "border-success-500/30 bg-success-500/5" :
                file.status === "error" ? "border-destructive/30 bg-destructive/5" :
                "border-border"
              }`}
            >
              <FileText className={`w-6 h-6 flex-shrink-0 ${
                file.status === "success" ? "text-success-500" :
                file.status === "error" ? "text-destructive" :
                file.status === "uploading" ? "text-primary animate-spin" :
                "text-muted-foreground"
              }`} />

              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm truncate">{file.name}</p>
                <p className="text-xs text-muted-foreground">{formatSize(file.size)}</p>
                {file.status === "uploading" && (
                  <div className="mt-2 h-1.5 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary transition-all duration-300"
                      style={{ width: `${file.progress}%` }}
                    />
                  </div>
                )}
                {file.status === "error" && file.error && (
                  <p className="mt-1 text-xs text-destructive flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" />
                    {file.error}
                  </p>
                )}
              </div>

              {file.status === "pending" && (
                <button
                  onClick={() => removeFile(file.id)}
                  className="text-muted-foreground hover:text-destructive transition-colors p-1"
                  aria-label="Remove file"
                >
                  <X className="w-5 h-5" />
                </button>
              )}

              {file.status === "success" && (
                <CheckCircle className="w-5 h-5 text-success-500 flex-shrink-0" />
              )}

              {file.status === "error" && (
                <button
                  onClick={() => removeFile(file.id)}
                  className="text-destructive hover:opacity-70 transition-opacity p-1"
                  aria-label="Remove failed file"
                >
                  <X className="w-5 h-5" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      {files.length > 0 && (
        <div className="flex flex-wrap items-center gap-4 pt-4 border-t border-border">
          <div className="flex-1 text-sm text-muted-foreground">
            {files.filter(f => f.status === "pending").length} pending &nbsp;•&nbsp;
            {files.filter(f => f.status === "uploading").length} uploading &nbsp;•&nbsp;
            {files.filter(f => f.status === "success").length} uploaded &nbsp;•&nbsp;
            {files.filter(f => f.status === "error").length} failed
          </div>

          <div className="flex items-center gap-2">
            {hasPending && !isUploading && (
              <button
                onClick={uploadAll}
                disabled={isUploading}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary-hover focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 disabled:opacity-50 transition-all flex items-center gap-2"
              >
                <Loader2 className="w-4 h-4" />
                Upload All
              </button>
            )}

            {isUploading && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin text-primary" />
                Uploading...
              </div>
            )}

            {allSuccess && (
              <button
                onClick={clearCompleted}
                className="px-4 py-2 bg-muted text-muted-foreground rounded-lg font-medium hover:bg-muted/80 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 transition-all"
              >
                Clear Completed
              </button>
            )}

            {hasErrors && (
              <button
                onClick={() => setFiles(prev => prev.filter(f => f.status !== "error"))}
                className="px-4 py-2 bg-destructive/10 text-destructive rounded-lg font-medium hover:bg-destructive/20 focus:outline-none focus:ring-2 focus:ring-destructive focus:ring-offset-2 transition-all"
              >
                Clear Errors
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}