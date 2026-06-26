import { useState } from "react";
import { uploadDocument } from "../services/api";
import type { UploadResponse } from "../types";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await uploadDocument(file);
      setResult(data);
      setFile(null);
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
        <p className="card-subtitle">Supported formats: PDF, DOCX, TXT</p>

        <div className={`upload-zone${file ? " has-file" : ""}`}>
          <input
            type="file"
            accept=".pdf,.docx,.txt"
            onChange={(e) => {
              setResult(null);
              setError(null);
              setFile(e.target.files?.[0] ?? null);
            }}
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

        <button
          className="btn btn-primary"
          onClick={handleUpload}
          disabled={!file || loading}
        >
          {loading ? (
            <>
              <span style={{ fontSize: "0.8rem" }}>⏳</span> Processing…
            </>
          ) : (
            <>
              <span>⬆</span> Upload & Process
            </>
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
              <span>Chunks stored</span>
              <strong>{result.chunks_stored}</strong>
            </div>
            <div className="alert-row">
              <span>Characters extracted</span>
              <strong>{result.characters.toLocaleString()}</strong>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

