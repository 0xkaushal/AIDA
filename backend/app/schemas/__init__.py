from pydantic import BaseModel
from typing import List


class UploadResponse(BaseModel):
    message: str
    filename: str
    chunks_stored: int
    characters: int


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[str]
