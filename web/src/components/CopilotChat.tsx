import { useEffect, useRef, useState } from "react";

import { api, type ToolCall } from "../api";
import { errorText, firstName } from "../lib";
import { useRecorder } from "./useRecorder";
import { Icon } from "./ui";

interface Message {
  from: "client" | "copilot" | "error";
  text: string;
  toolCalls?: ToolCall[];
}

const TOOL_LABEL: Record<string, string> = {
  schedule_meeting: "Reunião pré-agendada, aguardando confirmação",
  update_portfolio: "Pedido de alteração registrado",
};

const SUGGESTIONS = ["Quero agendar uma reunião", "Como está minha carteira hoje?"];

export function CopilotChat({ clientId, clientName }: { clientId: number; clientName: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const recorder = useRecorder(async (audio) => {
    setTranscribing(true);
    setVoiceError(null);
    try {
      const { text } = await api.transcribe(audio);
      if (!text.trim()) {
        setVoiceError("Não foi possível reconhecer a fala. Tente novamente ou digite a mensagem.");
      } else {
        setDraft((current) => (current.trim() ? `${current.trim()} ${text.trim()}` : text.trim()));
      }
    } catch (error) {
      setVoiceError(errorText(error));
    } finally {
      setTranscribing(false);
    }
  });

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [messages, busy]);

  // A conversa fica no backend: voltar para esta aba continua de onde parou.
  useEffect(() => {
    let cancelled = false;
    api.getChatHistory(clientId).then(
      (items) => {
        if (cancelled || items.length === 0) return;
        const past: Message[] = items.map((i) => ({
          from: i.role === "USER" ? "client" : "copilot",
          text: i.content,
          toolCalls: i.tool_calls,
        }));
        setMessages((now) => (now.length === 0 ? past : now));
      },
      () => undefined, // sem histórico a conversa só recomeça; o envio mostra o erro de verdade
    );
    return () => {
      cancelled = true;
    };
  }, [clientId]);

  async function send(text: string) {
    if (!text || busy) return;
    setDraft("");
    setMessages((m) => [...m, { from: "client", text }]);
    setBusy(true);
    try {
      const res = await api.sendChat({ client_id: clientId, message: text });
      setMessages((m) => [...m, { from: "copilot", text: res.reply, toolCalls: res.tool_calls }]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { from: "error", text: `A mensagem não foi enviada. Tente novamente. (${errorText(e)})` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel chat">
      <header className="panel-head">
        <h2>Conversar com o copiloto</h2>
        <p className="muted">
          Conte o que mudou ou o que precisa, {firstName(clientName)}. Para marcar uma reunião, o
          copiloto faz algumas perguntas para sua assessoria chegar preparada.
        </p>
      </header>

      <div className="thread" aria-live="polite">
        {messages.length === 0 && (
          <div className="suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" className="chip" onClick={() => send(s)}>
                {s}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`bubble bubble-${m.from}`}>
            {m.text}
            {m.toolCalls?.map((t, j) => (
              <span key={j} className="bubble-action">
                <Icon name="check" size={14} /> {TOOL_LABEL[t.name] ?? t.name}
              </span>
            ))}
          </div>
        ))}
        {busy && <div className="bubble bubble-copilot muted">Escrevendo…</div>}
        <div ref={endRef} />
      </div>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          send(draft.trim());
        }}
      >
        {recorder.supported && (
          <button
            type="button"
            className="btn btn-quiet"
            aria-label={recorder.recording ? "Parar gravação" : "Gravar mensagem"}
            title={recorder.recording ? "Parar gravação" : "Gravar mensagem"}
            disabled={busy || transcribing}
            onClick={recorder.recording ? recorder.stop : recorder.start}
          >
            <Icon name={recorder.recording ? "stop" : "mic"} />
          </button>
        )}
        <input
          aria-label="Mensagem para o copiloto"
          placeholder="Escreva uma mensagem"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <button
          className="btn btn-primary"
          type="submit"
          disabled={busy || transcribing || !draft.trim()}
        >
          <Icon name="send" /> Enviar
        </button>
      </form>
      {(recorder.recording || transcribing || recorder.error || voiceError) && (
        <p className={recorder.error || voiceError ? "state-error small" : "muted small"} role="status">
          {recorder.recording && `Gravando ${recorder.seconds}s`}
          {transcribing && "Transcrevendo áudio…"}
          {recorder.error || voiceError}
        </p>
      )}
      {!recorder.supported && (
        <p className="muted small" role="status">
          {recorder.unavailableMessage}
        </p>
      )}
    </section>
  );
}
