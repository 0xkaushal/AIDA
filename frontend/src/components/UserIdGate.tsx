import { useState } from "react";

const STORAGE_KEY = "aida_user_id";

export function getUserId(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

export function clearUserId() {
  localStorage.removeItem(STORAGE_KEY);
}

interface Props {
  onConfirm: (userId: string) => void;
}

export default function UserIdGate({ onConfirm }: Props) {
  const [input, setInput] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const id = input.trim();
    if (!id) {
      setError("Please enter a user ID.");
      return;
    }
    if (!/^[a-zA-Z0-9_-]{3,32}$/.test(id)) {
      setError("3–32 characters, letters, numbers, _ or - only.");
      return;
    }
    localStorage.setItem(STORAGE_KEY, id);
    onConfirm(id);
  };

  return (
    <div style={{
      minHeight: "100svh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "var(--bg)",
      padding: "1rem",
    }}>
      <div className="card" style={{ maxWidth: 400 }}>
        <div style={{ textAlign: "center", marginBottom: "1.5rem" }}>
          <div style={{
            width: 48, height: 48,
            background: "var(--accent)",
            borderRadius: 12,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "1.5rem", fontWeight: 800, color: "white",
            margin: "0 auto 1rem",
          }}>A</div>
          <h2 className="card-title" style={{ margin: 0 }}>Welcome to AIDA</h2>
          <p className="card-subtitle" style={{ marginTop: "0.375rem", marginBottom: 0 }}>
            Enter a user ID to keep your documents private
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <input
            autoFocus
            type="text"
            className="chat-textarea"
            style={{ marginBottom: "0.75rem", minHeight: "auto" }}
            placeholder="e.g. satvik or john_doe"
            value={input}
            onChange={(e) => { setInput(e.target.value); setError(""); }}
          />
          {error && (
            <div className="alert alert-error" style={{ marginBottom: "0.75rem", padding: "0.5rem 0.75rem" }}>
              {error}
            </div>
          )}
          <button type="submit" className="btn btn-primary">
            Get Started
          </button>
        </form>

        <p style={{ fontSize: "0.78rem", color: "var(--text)", opacity: 0.5, textAlign: "center", marginTop: "1rem", marginBottom: 0 }}>
          This ID is stored locally in your browser. Use the same ID to access your documents again.
        </p>
      </div>
    </div>
  );
}
