import { useState, useEffect, useCallback } from "react";
import { uploadDocument, listDocuments } from "../services/api";
import type { UploadResponse, DocumentInfo } from "../types";

export default function UploadPage({ userId }: { userId: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [confirmDuplicate, setConfirmDuplicate] = useState(false);
  const [visibility, setVisibility] = useState<"private" | "public">("private");

  const fetchDocuments = useCallback(async () => {
    try {
      const docs = await listDocuments(userId);
      setDocuments(docs);
    } catch {
      // silently fail — list is non-critical
    } finally {
      setDocsLoading(false);
    }
  }, []);

  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  const isDuplicate = (f: File) =>
    documents.some((d) => d.filename === f.name);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setResult(null);
    setError(null);
    setConfirmDuplicate(false);
    setVisibility("private");
    setFile(e.target.files?.[0] ?? null);
  };

  const handleUploadClick = () => {
    if (!file) return;
    if (!confirmDuplicate && isDuplicate(file)) {
      setConfirmDuplicate(true);
      return;
    }
    doUpload();
  };

  const doUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setConfirmDuplicate(false);
    try {
      const data = await uploadDocument(file, userId, visibility);
      setResult(data);
      setFile(null);
      fetchDocuments();
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Upload failed."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="card">
        <h2 className="card-title">Upload a Document</h2>
        <p className="card-subtitle">Supported formats: PDF, TXT</p>

        <div className={`upload-zone${file ? " has-file" : ""}`}>
          <input
            type="file"
            accept=".pdf,.txt"
            onChange={handleFileChange}
          />
          {file ? (
            <>
              <div className="upload-icon">📄</div>
              <div className="upload-zone-text"><strong>{file.name}</strong></div>
              <div className="upload-zone-hint">{(file.size / 1024).toFixed(1)} KB — click to change</div>
            </>
          ) : (
            <>
              <div className="upload-icon">📂</div>
              <div className="upload-zone-text">
                <strong>Click to choose a file</strong> or drag & drop
              </div>
              <div className="upload-zone-hint">PDF, DOCX or TXT up to 50 MB</div>
            </>
          )}
        </div>

        {file && (
          <div className="visibility-toggle">
            <button
              className={`visibility-btn${visibility === "private" ? " active" : ""}`}
              onClick={() => setVisibility("private")}
              type="button"
            >
              🔒 Private
            </button>
            <button
              className={`visibility-btn${visibility === "public" ? " active" : ""}`}
              onClick={() => setVisibility("public")}
              type="button"
            >
              🌐 Public
            </button>
          </div>
        )}

        {confirmDuplicate && (
          <div className="alert alert-error" style={{ marginBottom: "0.75rem" }}>
            <div className="alert-title">⚠️ Duplicate filename</div>
            <p style={{ margin: "0.25rem 0 0.75rem" }}>
              <strong>{file?.name}</strong> has already been uploaded. Re-uploading will add duplicate chunks to the index.
            </p>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button className="btn btn-primary" style={{ flex: 1 }} onClick={doUpload}>
                Upload anyway
              </button>
              <button
                className="btn"
                style={{ flex: 1, background: "var(--border)", color: "var(--text-h)" }}
                onClick={() => { setConfirmDuplicate(false); setFile(null); }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        <button
          className="btn btn-primary"
          onClick={handleUploadClick}
          disabled={!file || loading || confirmDuplicate}
        >
          {loading ? (
            <><span style={{ fontSize: "0.8rem" }}>⏳</span> Processing…</>
          ) : (
            <><span>⬆</span> Upload & Process</>
          )}
        </button>

        {error && (
          <div className="alert alert-error">
            <div className="alert-title">Upload failed</div>
            {error}
          </div>
        )}

        {result && (
          <div className="alert alert-success">
            <div className="alert-title">✓ {result.filename} processed</div>
            <div className="alert-row">
              <span>Chunks stored</span><strong>{result.chunks_stored}</strong>
            </div>
            <div className="alert-row">
              <span>Characters extracted</span><strong>{result.characters.toLocaleString()}</strong>
            </div>
            <div className="alert-row">
              <span>Visibility</span><strong>{result.visibility === "public" ? "🌐 Public" : "🔒 Private"}</strong>
            </div>
          </div>
        )}
      </div>

      <div className="card" style={{ marginTop: "1.5rem" }}>
        <h2 className="card-title" style={{ fontSize: "1rem", marginBottom: "1rem" }}>
          Uploaded Documents
          <span className="doc-count">{documents.length}</span>
        </h2>

        {docsLoading ? (
          <div className="doc-list-empty">Loading…</div>
        ) : documents.length === 0 ? (
          <div className="doc-list-empty">No documents uploaded yet.</div>
        ) : (
          <ul className="doc-list">
            {documents.map((doc) => (
              <li key={doc.filename} className="doc-item">
                <div className="doc-icon">📄</div>
                <div className="doc-meta">
                  <div className="doc-name">{doc.filename}</div>
                  <div className="doc-details">
                    {doc.chunks_stored} chunks · {doc.characters.toLocaleString()} chars ·{" "}
                    {new Date(doc.uploaded_at).toLocaleString()} ·{" "}
                    {doc.visibility === "public" ? "🌐 Public" : "🔒 Private"}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

