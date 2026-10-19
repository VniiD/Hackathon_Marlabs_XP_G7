import { useEffect, useRef, useState } from "react";

import { api, type ToolCall } from "../api";
import { errorText, firstName } from "../lib";
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
  const endRef = useRef<HTMLDivElement>(null);

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
        <input
          aria-label="Mensagem para o copiloto"
          placeholder="Escreva uma mensagem"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <button className="btn btn-primary" type="submit" disabled={busy || !draft.trim()}>
          <Icon name="send" /> Enviar
        </button>
      </form>
    </section>
  );
}
