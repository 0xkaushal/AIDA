from fastapi import FastAPI
from core.config import settings
from api.routes import health, documents, chat

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
