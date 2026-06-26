export interface UploadResponse {
  message: string;
  filename: string;
  chunks_stored: number;
  characters: number;
  visibility: string;
}

export interface DocumentInfo {
  filename: string;
  chunks_stored: number;
  characters: number;
  uploaded_at: string;
  visibility?: string;
}

export interface ChatRequest {
  question: string;
  user_id: string;
}

export interface ChatResponse {
  answer: string;
  sources: string[];
}
