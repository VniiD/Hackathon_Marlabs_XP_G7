from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool

from src.modules.copilot_chat.models import ChatHistoryItem, ChatRequest, ChatResponse, Transcript
from src.modules.copilot_chat.services import CopilotChatService, get_copilot_service
from src.modules.copilot_chat.transcription import (
    TranscriptionService,
    get_transcription_service,
)

router = APIRouter(prefix="/copilot", tags=["copilot_chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest, svc: CopilotChatService = Depends(get_copilot_service)
) -> ChatResponse:
    return svc.handle(req)


@router.get("/chat/{client_id}/history", response_model=list[ChatHistoryItem])
def history(
    client_id: int, svc: CopilotChatService = Depends(get_copilot_service)
) -> list[ChatHistoryItem]:
    return svc.history(client_id)


@router.post("/transcribe", response_model=Transcript)
async def transcribe(
    request: Request, svc: TranscriptionService = Depends(get_transcription_service)
) -> Transcript:
    """Recebe o áudio cru no corpo (webm, ogg, mp4 ou wav) e devolve o texto."""
    audio = await request.body()
    return await run_in_threadpool(svc.transcribe, audio)
