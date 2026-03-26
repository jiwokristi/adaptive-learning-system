"use client";

import { useState, useEffect, useCallback } from "react";
import { uploadDocument, listDocuments, type Document } from "@/lib/api";

// MVP: hardcoded user ID (no auth yet)
const USER_ID = "00000000-0000-0000-0000-000000000001";

export default function HomePage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDocuments = useCallback(async () => {
    try {
      const docs = await listDocuments(USER_ID);
      setDocuments(docs);
    } catch {
      // API might not be running yet
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
    // Poll for status updates on processing documents
    const interval = setInterval(fetchDocuments, 5000);
    return () => clearInterval(interval);
  }, [fetchDocuments]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    try {
      await uploadDocument(file, USER_ID);
      await fetchDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  const statusColor: Record<string, string> = {
    uploaded: "bg-gray-100 text-gray-700",
    ingesting: "bg-blue-100 text-blue-700",
    distilling: "bg-yellow-100 text-yellow-700",
    ready: "bg-green-100 text-green-700",
    error: "bg-red-100 text-red-700",
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold">Your Documents</h1>
        <label className="cursor-pointer bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors">
          {uploading ? "Uploading..." : "Upload PDF"}
          <input
            type="file"
            accept=".pdf"
            onChange={handleUpload}
            disabled={uploading}
            className="hidden"
          />
        </label>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
          {error}
        </div>
      )}

      {documents.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <p className="text-lg mb-2">No documents yet</p>
          <p className="text-sm">Upload a PDF to get started</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {documents.map((doc) => (
            <a
              key={doc.id}
              href={doc.status === "ready" ? `/documents/${doc.id}` : "#"}
              className={`block bg-white border border-gray-200 rounded-lg p-5 transition-colors ${
                doc.status === "ready"
                  ? "hover:border-blue-300 cursor-pointer"
                  : "cursor-default"
              }`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-lg">{doc.filename}</h2>
                  <p className="text-sm text-gray-500 mt-1">
                    {doc.page_count ? `${doc.page_count} pages` : "Processing..."}
                    {doc.topic_count != null &&
                      ` \u00b7 ${doc.topic_count} topics \u00b7 ${doc.concept_count} concepts`}
                  </p>
                </div>
                <span
                  className={`text-xs font-medium px-3 py-1 rounded-full ${
                    statusColor[doc.status] || "bg-gray-100"
                  }`}
                >
                  {doc.status}
                </span>
              </div>
              {doc.error_message && (
                <p className="text-sm text-red-600 mt-2">{doc.error_message}</p>
              )}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
