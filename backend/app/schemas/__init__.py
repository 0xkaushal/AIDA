from pydantic import BaseModel, Field
from typing import List
from datetime import datetime


class UploadResponse(BaseModel):
    message: str
    filename: str
    chunks_stored: int
    characters: int
    visibility: str


class DocumentInfo(BaseModel):
    filename: str
    chunks_stored: int
    characters: int
    uploaded_at: datetime
    visibility: str = "private"


class DocumentListResponse(BaseModel):
    documents: List[DocumentInfo]


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatHistoryResponse(BaseModel):
    messages: List[ChatMessage]


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[str]
