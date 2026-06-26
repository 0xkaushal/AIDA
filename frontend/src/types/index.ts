export interface UploadResponse {
  message: string;
  filename: string;
  chunks_stored: number;
  characters: number;
}

export interface ChatRequest {
  question: string;
}

export interface ChatResponse {
  answer: string;
  sources: string[];
}
