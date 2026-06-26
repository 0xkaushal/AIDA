from pydantic import BaseModel
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


class DocumentListResponse(BaseModel):
    documents: List[DocumentInfo]


class ChatRequest(BaseModel):
    question: str
    user_id: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[str]
