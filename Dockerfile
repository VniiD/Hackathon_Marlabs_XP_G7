FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	HF_HOME=/opt/huggingface

WORKDIR /app

RUN apt-get update \
	&& apt-get install --no-install-recommends -y libgomp1 \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cacheia o modelo open source no build da imagem para evitar download na primeira gravação.
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-tiny', local_dir='/opt/models/faster-whisper-tiny')"

COPY . .

RUN useradd --create-home --uid 10001 appuser \
	&& chown -R appuser:appuser /app

ENV WHISPER_MODEL=/opt/models/faster-whisper-tiny

EXPOSE 8000
USER 10001:10001
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
