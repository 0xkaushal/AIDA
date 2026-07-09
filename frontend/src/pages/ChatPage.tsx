import { useState, useRef, useEffect } from "react";
import { streamQuestion, getChatHistory } from "../services/api";

interface Message {
  role: "user" | "ai";
  content: string;
  sources?: string[];
}

export default function ChatPage({ userId }: { userId: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingSources, setStreamingSources] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Load history from backend on mount
  useEffect(() => {
    getChatHistory(userId)
      .then((msgs) => {
        setMessages(
          msgs.map((m) => ({
            role: m.role === "assistant" ? "ai" : "user",
            content: m.content,
            sources: m.sources,
          }))
        );
      })
      .catch(() => {/* backend not available — start fresh */})
      .finally(() => setHistoryLoading(false));
  }, [userId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async () => {
    const question = input.trim();
    if (!question || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setLoading(true);
    setStreamingContent("");
    setStreamingSources([]);

    // Local accumulators avoid stale-closure issues when building the final message
    let finalContent = "";
    let finalSources: string[] = [];

    try {
      await streamQuestion(
        { question, user_id: userId },
        (token) => {
          finalContent += token;
          setStreamingContent((prev) => prev + token);
        },
        (sources) => {
          finalSources = sources;
          setStreamingSources(sources);
        },
      );
      setMessages((prev) => [
        ...prev,
        { role: "ai", content: finalContent, sources: finalSources },
      ]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Something went wrong.";
      setMessages((prev) => [
        ...prev,
        { role: "ai", content: `⚠️ ${msg}` },
      ]);
    } finally {
      setLoading(false);
      setStreamingContent("");
      setStreamingSources([]);
      textareaRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-page">
      <div className="chat-messages">
        {messages.length === 0 && !loading && (
          <div className="chat-empty">
            <div className="chat-empty-icon">💬</div>
            <div className="chat-empty-text">
              {historyLoading
                ? "Loading history…"
                : "Upload a document, then ask questions about it"}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`message message-${msg.role}`}>
            <div className="message-avatar">
              {msg.role === "user" ? "You" : "AI"}
            </div>
            <div>
              <div className="message-bubble">{msg.content}</div>
              {msg.sources && msg.sources.length > 0 && (
                <div className="message-sources">
                  Sources:{" "}
                  {msg.sources.map((s, j) => (
                    <span key={j}>{s}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="message message-ai">
            <div className="message-avatar">AI</div>
            <div>
              <div className="message-bubble">
                {streamingContent ? (
                  streamingContent
                ) : (
                  <div className="typing-dots">
                    <span /><span /><span />
                  </div>
                )}
              </div>
              {streamingSources.length > 0 && (
                <div className="message-sources">
                  Sources:{" "}
                  {streamingSources.map((s, j) => (
                    <span key={j}>{s}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="chat-input-bar">
        <div className="chat-input-wrap">
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            rows={1}
            placeholder="Ask a question about your documents… (Enter to send)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
          />
        </div>
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={!input.trim() || loading}
          title="Send"
        >
          ➤
        </button>
      </div>
    </div>
  );
}

