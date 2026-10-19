import time

import httpx

from src.core.config import Settings, get_settings
from src.core.exceptions import DomainError, ExternalServiceError
from src.modules.copilot_chat.models import Transcript

MAX_AUDIO_BYTES = 25 * 1024 * 1024
ASSEMBLYAI_URL = "https://api.assemblyai.com/v2"
POLL_SECONDS = 1.0
POLL_TIMEOUT_SECONDS = 90


class TranscriptionService:
    """Transcreve áudio em português pela AssemblyAI."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.assemblyai_api_key

    def transcribe(self, audio: bytes) -> Transcript:
        if not audio:
            raise DomainError("Nenhum áudio recebido")
        if len(audio) > MAX_AUDIO_BYTES:
            raise DomainError("Áudio muito longo; grave em partes de até 3 minutos")
        if not self._api_key:
            raise ExternalServiceError("Transcrição não configurada: defina ASSEMBLYAI_API_KEY")
        try:
            return self._request(audio)
        except httpx.HTTPError as exc:
            raise ExternalServiceError("A AssemblyAI não respondeu") from exc

    def _request(self, audio: bytes) -> Transcript:
        headers = {"authorization": self._api_key}
        with httpx.Client(base_url=ASSEMBLYAI_URL, headers=headers, timeout=60) as http:
            upload = http.post("/upload", content=audio)
            upload.raise_for_status()
            job = http.post(
                "/transcript",
                json={"audio_url": upload.json()["upload_url"], "language_code": "pt"},
            )
            job.raise_for_status()
            # A transcrição é assíncrona: consulta até concluir ou estourar o prazo.
            deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                result = http.get(f"/transcript/{job.json()['id']}")
                result.raise_for_status()
                body = result.json()
                if body["status"] == "completed":
                    return Transcript(
                        text=(body.get("text") or "").strip(),
                        duration_seconds=float(body.get("audio_duration") or 0),
                    )
                if body["status"] == "error":
                    raise ExternalServiceError(f"AssemblyAI: {body.get('error')}")
                time.sleep(POLL_SECONDS)
        raise ExternalServiceError("A AssemblyAI demorou demais para responder")


def get_transcription_service() -> TranscriptionService:
    return TranscriptionService(get_settings())
