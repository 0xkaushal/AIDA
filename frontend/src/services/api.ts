import axios from "axios";
import type { UploadResponse, ChatRequest, ChatResponse } from "../types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
});

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post<UploadResponse>(
    "/api/v1/documents/upload",
    formData
  );
  return data;
}

export async function askQuestion(request: ChatRequest): Promise<ChatResponse> {
  const { data } = await api.post<ChatResponse>("/api/v1/chat/ask", request);
  return data;
}
