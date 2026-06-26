from fastapi import APIRouter, HTTPException
from schemas import ChatRequest, ChatResponse
from services.ai_service import answer_question

router = APIRouter()


@router.post("/ask", response_model=ChatResponse)
def ask(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    result = answer_question(request.question)
    return ChatResponse(**result)
