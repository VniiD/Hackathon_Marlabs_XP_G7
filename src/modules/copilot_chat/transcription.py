import logging
from functools import lru_cache
from io import BytesIO

from src.core.config import Settings, get_settings
from src.core.exceptions import DomainError, ExternalServiceError
from src.modules.copilot_chat.models import Transcript

MAX_AUDIO_BYTES = 25 * 1024 * 1024
logger = logging.getLogger("uvicorn.error")


class TranscriptionService:
    """Transcreve áudio em português localmente com faster-whisper."""

    def __init__(self, settings: Settings, model=None) -> None:
        self._model_name = settings.whisper_model
        self._model = model

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel  # type: ignore[import-untyped]

            self._model = WhisperModel(
                self._model_name,
                device="cpu",
                compute_type="int8",
            )
        return self._model

    def transcribe(self, audio: bytes) -> Transcript:
        if not audio:
            raise DomainError("Nenhum áudio recebido")
        if len(audio) > MAX_AUDIO_BYTES:
            raise DomainError("Áudio muito longo; grave em partes de até 3 minutos")
        try:
            segments, info = self._get_model().transcribe(
                BytesIO(audio),
                language="pt",
                vad_filter=True,
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
            return Transcript(text=text, duration_seconds=float(info.duration or 0))
        except DomainError:
            raise
        except Exception as exc:
            logger.exception("Falha no motor local de transcrição")
            raise ExternalServiceError(
                "Não foi possível transcrever o áudio. Confira o formato e tente novamente."
            ) from exc


@lru_cache(maxsize=1)
def get_transcription_service() -> TranscriptionService:
    return TranscriptionService(get_settings())
