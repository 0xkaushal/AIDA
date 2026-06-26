import axios from "axios";
import type { UploadResponse, ChatRequest, ChatResponse, DocumentInfo } from "../types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
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
