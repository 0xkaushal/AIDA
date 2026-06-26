export interface UploadResponse {
  message: string;
  filename: string;
  chunks_stored: number;
  characters: number;
}

export interface DocumentInfo {
  filename: string;
  chunks_stored: number;
  characters: number;
  uploaded_at: string;
}

export interface ChatRequest {
  question: string;
}

export interface ChatResponse {
  answer: string;
  sources: string[];
}
