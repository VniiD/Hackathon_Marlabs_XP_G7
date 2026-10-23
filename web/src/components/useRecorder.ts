import { useEffect, useRef, useState } from "react";

const MAX_SECONDS = 180;

function microphoneError(error: unknown): string {
  const name = error instanceof DOMException ? error.name : "";
  if (name === "NotFoundError" || name === "DevicesNotFoundError") {
    return "Microfone ausente. Conecte ou habilite um microfone e tente novamente.";
  }
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "Acesso ao microfone negado. Permita o uso do microfone no navegador.";
  }
  if (name === "NotReadableError" || name === "TrackStartError") {
    return "Microfone não está ativo ou está sendo usado por outro aplicativo.";
  }
  return "Microfone indisponível. Verifique o dispositivo e a permissão do navegador.";
}

/** Grava o microfone e entrega o áudio pronto ao parar. */
export function useRecorder(onAudio: (audio: Blob) => void) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const timer = useRef<number>();
  const deliver = useRef(onAudio);
  deliver.current = onAudio;

  const supported =
    typeof MediaRecorder !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia);

  function stop() {
    window.clearInterval(timer.current);
    if (recorder.current?.state === "recording") recorder.current.stop();
  }

  async function start() {
    setError(null);
    if (!supported) {
      setError("Microfone ausente ou não suportado neste navegador. Você pode escrever a resposta.");
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (cause) {
      setError(microphoneError(cause));
      return;
    }
    const chunks: Blob[] = [];
    let rec: MediaRecorder;
    try {
      rec = new MediaRecorder(stream);
    } catch (cause) {
      stream.getTracks().forEach((track) => track.stop());
      setError(microphoneError(cause));
      return;
    }
    rec.ondataavailable = (e) => e.data.size > 0 && chunks.push(e.data);
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      setRecording(false);
      deliver.current(new Blob(chunks, { type: rec.mimeType }));
    };
    recorder.current = rec;
    rec.start();
    setSeconds(0);
    setRecording(true);
    timer.current = window.setInterval(() => {
      setSeconds((s) => {
        if (s + 1 >= MAX_SECONDS) stop();
        return s + 1;
      });
    }, 1000);
  }

  // Sair da tela no meio da gravação solta o microfone.
  useEffect(() => stop, []);

  return {
    supported,
    unavailableMessage: "Microfone ausente ou não suportado. Escreva sua mensagem.",
    recording,
    seconds,
    error,
    start,
    stop,
    maxSeconds: MAX_SECONDS,
  };
}
