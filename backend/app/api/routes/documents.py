from fastapi import APIRouter, UploadFile, File, HTTPException
from schemas import UploadResponse
from services.document_service import process_document

router = APIRouter()

ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
}


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Only PDF and TXT are allowed.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        result = process_document(file_bytes, file.filename, file.content_type)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return UploadResponse(
        message="Document processed and stored successfully.",
        **result,
    )
