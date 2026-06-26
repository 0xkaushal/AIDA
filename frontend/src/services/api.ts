import axios from "axios";
import type { UploadResponse, ChatRequest, ChatResponse, DocumentInfo } from "../types";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000") as string;

const api = axios.create({
  baseURL: BASE_URL,
});

export async function listDocuments(userId: string): Promise<DocumentInfo[]> {
  const { data } = await api.get<{ documents: DocumentInfo[] }>("/api/v1/documents/", {
    params: { user_id: userId },
  });
  return data.documents;
}

export async function uploadDocument(file: File, userId: string, visibility: "public" | "private"): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post<UploadResponse>(
    "/api/v1/documents/upload",
    formData,
    { params: { user_id: userId, visibility } }
  );
  return data;
}

export async function getChatHistory(userId: string): Promise<{ role: string; content: string }[]> {
  const { data } = await api.get<{ messages: { role: string; content: string }[] }>(
    "/api/v1/chat/history",
    { params: { user_id: userId } }
  );
  return data.messages;
}

export async function askQuestion(request: ChatRequest): Promise<ChatResponse> {
  const { data } = await api.post<ChatResponse>("/api/v1/chat/ask", request);
  return data;
}

export async function streamQuestion(
  request: ChatRequest,
  onToken: (token: string) => void,
  onSources: (sources: string[]) => void,
): Promise<void> {
  const response = await fetch(`${BASE_URL}/api/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error((err as { detail?: string }).detail ?? "Request failed");
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const raw = line.slice(6);
      if (raw === "[DONE]") return;
      try {
        const payload = JSON.parse(raw) as { type: string; token?: string; sources?: string[]; message?: string };
        if (payload.type === "token" && payload.token) onToken(payload.token);
        else if (payload.type === "sources" && payload.sources) onSources(payload.sources);
        else if (payload.type === "error") throw new Error(payload.message ?? "Unknown error");
      } catch (e) {
        if (e instanceof Error && e.message !== raw) throw e; // rethrow intentional errors
        // malformed SSE line — skip
      }
    }
  }
}
