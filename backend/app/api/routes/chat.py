from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from schemas import ChatRequest, ChatResponse, ChatHistoryResponse, ChatMessage # type: ignore
from services.ai_service import answer_question, clear_history, get_history, stream_answer_question # type: ignore

router = APIRouter()


@router.get("/history", response_model=ChatHistoryResponse)
def history(user_id: str):
    return ChatHistoryResponse(
        messages=[ChatMessage(**m) for m in get_history(user_id)]
    )


# Non-streaming fallback — kept for direct API testing via /docs and as a
# reference implementation. The UI calls POST /stream instead.
@router.post("/ask", response_model=ChatResponse)
def ask(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if not request.user_id.strip():
        raise HTTPException(status_code=400, detail="user_id cannot be empty.")

    result = answer_question(request.question, request.user_id)
    return ChatResponse(**result)


@router.delete("/history")
def delete_history(user_id: str):
    clear_history(user_id)
    return {"message": "Chat history cleared."}


@router.post("/stream")
async def ask_stream(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if not request.user_id.strip():
        raise HTTPException(status_code=400, detail="user_id cannot be empty.")
    return StreamingResponse(
        stream_answer_question(request.question, request.user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering in Docker
        },
    )
