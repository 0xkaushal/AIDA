from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from schemas import UploadResponse, DocumentListResponse, DocumentInfo # type: ignore
from services.document_service import process_document, list_documents # type: ignore

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
}


@router.get("/", response_model=DocumentListResponse)
async def get_documents(user_id: str = Query(..., min_length=1)):
    return DocumentListResponse(
        documents=[DocumentInfo(**d) for d in list_documents(user_id)]
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Query(..., min_length=1),
    visibility: str = Query(default="private", pattern="^(public|private)$"),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Only PDF and TXT are allowed.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum allowed size is 10 MB.",
        )

    try:
        result = process_document(file_bytes, file.filename, file.content_type, user_id, visibility)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return UploadResponse(
        message="Document processed and stored successfully.",
        **result,
    )
