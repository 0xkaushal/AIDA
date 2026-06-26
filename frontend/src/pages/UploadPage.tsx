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
    <div style={{ maxWidth: 600, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h1>Upload Document</h1>
      <p>Supported formats: PDF, TXT</p>

      <input
        type="file"
        accept=".pdf,.txt"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />
      <br />
      <br />
      <button onClick={handleUpload} disabled={!file || loading}>
        {loading ? "Uploading…" : "Upload & Process"}
      </button>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {result && (
        <div style={{ marginTop: "1rem", background: "#f0f0f0", padding: "1rem", borderRadius: 8 }}>
          <p>✅ <strong>{result.filename}</strong> processed successfully</p>
          <p>Chunks stored: {result.chunks_stored}</p>
          <p>Characters extracted: {result.characters}</p>
        </div>
      )}
    </div>
  );
}
