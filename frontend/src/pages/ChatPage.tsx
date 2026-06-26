import { useState } from "react";
import { askQuestion } from "../services/api";
import type { ChatResponse } from "../types";

export default function ChatPage() {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleAsk = async () => {
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    setResponse(null);
    try {
      const data = await askQuestion({ question });
      setResponse(data);
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Something went wrong."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 700, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h1>Ask Your Documents</h1>

      <textarea
        rows={3}
        style={{ width: "100%", padding: "0.5rem", fontSize: "1rem" }}
        placeholder="Ask a question about your uploaded documents…"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleAsk()}
      />
      <br />
      <button onClick={handleAsk} disabled={!question.trim() || loading}>
        {loading ? "Thinking…" : "Ask"}
      </button>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {response && (
        <div style={{ marginTop: "1.5rem" }}>
          <div style={{ background: "#eef6ff", padding: "1rem", borderRadius: 8 }}>
            <strong>Answer:</strong>
            <p style={{ whiteSpace: "pre-wrap" }}>{response.answer}</p>
          </div>
          {response.sources.length > 0 && (
            <div style={{ marginTop: "0.5rem", color: "#555" }}>
              <strong>Sources:</strong> {response.sources.join(", ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
