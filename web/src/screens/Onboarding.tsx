import { useEffect, useRef, useState } from "react";

import { api, type LoginProfile, type Suitability, type SuitabilityAnswer } from "../api";
import { Icon } from "../components/ui";
import { useRecorder } from "../components/useRecorder";
import { APP_NAME, RISK_HINT, RISK_LABEL, errorText, firstName } from "../lib";
import { QUESTIONS, REQUIRED, coveredTopics, type Question } from "../questions";

interface Props {
  profile: LoginProfile;
  onEnter: () => void;
  onExit: () => void;
}

const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

interface AnswerFormProps {
  clientId: number;
  question: Question;
  saved?: SuitabilityAnswer;
  onSaved: (suitability: Suitability) => void;
  onNext: () => void;
}

type SaveStatus = "idle" | "saving" | "saved" | "error";

const AUTOSAVE_MS = 700;

function AnswerForm({ clientId, question, saved, onSaved, onNext }: AnswerFormProps) {
  const [text, setText] = useState(saved?.answer ?? "");
  const [option, setOption] = useState<number | null>(saved?.option_index ?? null);
  const [transcribing, setTranscribing] = useState(false);
  const [status, setStatus] = useState<SaveStatus>(saved ? "saved" : "idle");
  const [note, setNote] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const snapshot = (value: string, choice: number | null) => JSON.stringify([value.trim(), choice]);
  const latest = useRef({ text, option });
  latest.current = { text, option };
  const lastSaved = useRef(snapshot(text, option));
  const queue = useRef<Promise<unknown>>(Promise.resolve());

  // Salva o estado atual; chamadas em fila para a última escrita sempre vencer.
  function flush() {
    const current = latest.current;
    const key = snapshot(current.text, current.option);
    if (key === lastSaved.current) return;
    lastSaved.current = key;
    const answer = current.text.trim();
    const empty = !answer && current.option === null;
    setStatus("saving");
    queue.current = queue.current
      .then(() =>
        empty
          ? api.clearSuitabilityAnswer(clientId, question.id)
          : api.answerSuitability(clientId, {
              question_id: question.id,
              answer,
              option_index: current.option,
            }),
      )
      .then((suitability) => {
        onSaved(suitability);
        setStatus(empty ? "idle" : "saved");
      })
      .catch(() => {
        lastSaved.current = "";
        setStatus("error");
      });
  }

  useEffect(() => {
    const id = window.setTimeout(flush, AUTOSAVE_MS);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, option]);

  // Ao trocar de pergunta, salva na hora o que ainda estava pendente.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => flush, []);

  const recorder = useRecorder(async (audio) => {
    setTranscribing(true);
    setNote(null);
    try {
      const { text: spoken } = await api.transcribe(audio);
      if (!spoken) {
        setNote({ kind: "error", text: "Não deu para entender o áudio. Grave de novo, mais perto do microfone." });
      } else {
        setText((t) => (t.trim() ? `${t.trim()} ${spoken}` : spoken));
        setNote({ kind: "ok", text: "Transcrição adicionada. Se saiu errado, limpe e grave de novo." });
      }
    } catch {
      setNote({
        kind: "error",
        text: "A transcrição não respondeu. Tente gravar de novo ou escreva a resposta.",
      });
    } finally {
      setTranscribing(false);
    }
  });

  const covered = coveredTopics(question, text);
  const missing = question.topics.filter((_, i) => !covered[i]);
  const hasText = text.trim().length > 0;
  const busy = recorder.recording || transcribing;

  return (
    <div className="q">
      {question.quick && (
        <fieldset className="q-quick">
          <legend>{question.quick.label}</legend>
          <div className="suggestions">
            {question.quick.options.map((label, i) => (
              <button
                key={label}
                type="button"
                className={option === i ? "chip is-on" : "chip"}
                aria-pressed={option === i}
                onClick={() => setOption(i)}
              >
                {label}
              </button>
            ))}
          </div>
        </fieldset>
      )}

      <div className="q-body">
        <div className="q-topics">
          <h2>{question.quick ? "Conte mais, falando ou escrevendo" : "Fale ou escreva sobre"}</h2>
          <ul>
            {question.topics.map((t, i) => (
              <li key={t.label} className={covered[i] ? "is-done" : ""}>
                <span className="q-check" aria-hidden="true">
                  {covered[i] && <Icon name="check" size={12} />}
                </span>
                {t.label}
                <span className="sr-only">{covered[i] ? " (já mencionado)" : " (falta mencionar)"}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="q-answer">
          <label>
            Sua resposta
            <textarea
              rows={7}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Grave um áudio seguindo os tópicos ao lado, ou escreva aqui."
              disabled={transcribing}
            />
          </label>

          <div className="rec">
            {recorder.supported &&
              (recorder.recording ? (
                <button type="button" className="btn rec-stop" onClick={recorder.stop}>
                  <Icon name="stop" /> Parar e transcrever
                </button>
              ) : (
                <button type="button" className="btn" onClick={recorder.start} disabled={busy}>
                  <Icon name="mic" /> {hasText ? "Gravar mais um trecho" : "Gravar resposta"}
                </button>
              ))}
            {hasText && !busy && (
              <button
                type="button"
                className="btn btn-quiet"
                onClick={() => {
                  setText("");
                  setNote(null);
                }}
              >
                <Icon name="trash" size={16} /> Limpar resposta
              </button>
            )}
            <span className="rec-status" role="status">
              {recorder.recording && (
                <>
                  <span className="rec-dot" aria-hidden="true" />
                  Gravando {clock(recorder.seconds)} de {clock(recorder.maxSeconds)}
                </>
              )}
              {transcribing && "Transcrevendo o áudio…"}
              {!busy && status === "saving" && "Salvando…"}
              {!busy && status === "saved" && (
                <>
                  <Icon name="check" size={14} /> Salvo automaticamente
                </>
              )}
            </span>
          </div>

          {!recorder.supported && (
            <p className="muted small">Este navegador não grava áudio. Escreva a resposta.</p>
          )}
          {recorder.error && (
            <p className="state-error" role="alert">
              {recorder.error}
            </p>
          )}
          {status === "error" && (
            <p className="state-error" role="alert">
              A resposta não foi salva.{" "}
              <button type="button" className="link" onClick={flush}>
                Tentar de novo
              </button>
            </p>
          )}
          {note && (
            <p className={note.kind === "ok" ? "ok" : "state-error"} role={note.kind === "ok" ? "status" : "alert"}>
              {note.text}
            </p>
          )}
          {hasText && missing.length > 0 && !busy && (
            <p className="muted small">
              Ainda não apareceu na resposta: {missing.map((t) => t.label.toLowerCase()).join("; ")}.
            </p>
          )}
        </div>
      </div>

      <div className="q-actions">
        <button type="button" className="btn btn-primary" disabled={busy} onClick={onNext}>
          Próxima pergunta
        </button>
        {question.quick && option === null && (
          <span className="muted small">Esta é obrigatória: escolha uma das opções acima.</span>
        )}
      </div>
    </div>
  );
}

export function Onboarding({ profile, onEnter, onExit }: Props) {
  const [suit, setSuit] = useState<Suitability | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Muda a cada "recomeçar", para o formulário aberto ser recriado vazio.
  const [round, setRound] = useState(0);

  useEffect(() => {
    api
      .getSuitability(profile.id)
      .then((s) => {
        setSuit(s);
        const done = new Set(s.answers.map((a) => a.question_id));
        setActiveId(QUESTIONS.find((q) => !done.has(q.id))?.id ?? null);
      })
      .catch((e) => setLoadError(errorText(e)));
  }, [profile.id]);

  const answers = new Map((suit?.answers ?? []).map((a) => [a.question_id, a]));
  const active = QUESTIONS.find((q) => q.id === activeId);
  const requiredDone = REQUIRED.filter((q) => answers.get(q.id)?.option_index != null).length;
  const unlocked = Boolean(suit?.risk_profile);

  // Próxima pergunta ainda sem resposta; null quando todas as outras já têm.
  function goNext(from: Question) {
    const index = QUESTIONS.indexOf(from);
    const order = [...QUESTIONS.slice(index + 1), ...QUESTIONS.slice(0, index)];
    setActiveId(order.find((q) => !answers.has(q.id))?.id ?? null);
  }

  async function restart() {
    if (!window.confirm("Apagar todas as respostas e recomeçar a análise de perfil?")) return;
    try {
      setSuit(await api.resetSuitability(profile.id));
      setActiveId(QUESTIONS[0].id);
      setRound((r) => r + 1);
    } catch (e) {
      setLoadError(errorText(e));
    }
  }

  return (
    <div className="onb">
      <header className="onb-top">
        <span className="brand">{APP_NAME}</span>
        <button type="button" className="btn btn-quiet" onClick={onExit}>
          Trocar de perfil
        </button>
      </header>

      <div className="onb-body">
        <main className="onb-main">
          {loadError && (
            <p className="state state-error" role="alert">
              Não foi possível carregar a análise de perfil. Tente novamente.
            </p>
          )}
          {!suit && !loadError && (
            <p className="state" role="status">
              Carregando a análise de perfil…
            </p>
          )}

          {suit && active && (
            <>
              <p className="muted">
                Pergunta {QUESTIONS.indexOf(active) + 1} de {QUESTIONS.length}{" "}
                <span className={active.required ? "tag tag-accent" : "tag"}>
                  {active.required ? "Obrigatória" : "Opcional"}
                </span>
              </p>
              <h1>{active.text}</h1>
              <AnswerForm
                key={`${active.id}-${round}`}
                clientId={profile.id}
                question={active}
                saved={answers.get(active.id)}
                onSaved={setSuit}
                onNext={() => goNext(active)}
              />
            </>
          )}

          {suit && !active && (
            <div className="onb-end">
              <h1>
                {answers.size === QUESTIONS.length
                  ? `Tudo respondido, ${firstName(profile.name)}`
                  : "Por enquanto é isso"}
              </h1>
              <p className="muted">
                {unlocked
                  ? "Sua assessoria já tem acesso às respostas. Para rever ou completar alguma, escolha na lista ao lado."
                  : "Faltam perguntas obrigatórias. Escolha uma na lista ao lado para responder."}
              </p>
            </div>
          )}
        </main>

        <aside className="onb-side">
          <h2>Análise de perfil</h2>
          <div
            className="steps"
            role="img"
            aria-label={`${requiredDone} de ${REQUIRED.length} perguntas obrigatórias respondidas`}
          >
            {REQUIRED.map((q) => (
              <span key={q.id} className={answers.has(q.id) ? "step is-done" : "step"} />
            ))}
          </div>
          <p className="muted small">
            {requiredDone} de {REQUIRED.length} obrigatórias, {answers.size} de {QUESTIONS.length} no
            total
          </p>

          <ol className="onb-list">
            {QUESTIONS.map((q) => {
              const answer = answers.get(q.id);
              const covered = answer ? coveredTopics(q, answer.answer).filter(Boolean).length : 0;
              return (
                <li key={q.id}>
                  <button
                    type="button"
                    className={q.id === activeId ? "onb-item is-active" : "onb-item"}
                    aria-current={q.id === activeId ? "step" : undefined}
                    onClick={() => setActiveId(q.id)}
                  >
                    <span className={answer ? "q-check is-done" : "q-check"} aria-hidden="true">
                      {answer && <Icon name="check" size={12} />}
                    </span>
                    <span className="onb-item-name">{q.short}</span>
                    <span className="muted small">
                      {answer
                        ? `${covered} de ${q.topics.length} tópicos`
                        : q.required
                          ? "Obrigatória"
                          : "Opcional"}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>

          {suit?.risk_profile && (
            <div className="verdict" role="status">
              <span className="muted small">Seu perfil de investidor</span>
              <strong>{RISK_LABEL[suit.risk_profile]}</strong>
              <p className="small">{RISK_HINT[suit.risk_profile]}</p>
            </div>
          )}

          <button type="button" className="btn btn-primary btn-block" disabled={!unlocked} onClick={onEnter}>
            Entrar na plataforma
          </button>
          <p className="muted small">
            {unlocked
              ? "Você pode voltar e completar as respostas quando quiser."
              : "Responda as perguntas obrigatórias para liberar o acesso."}
          </p>
          {answers.size > 0 && (
            <button type="button" className="btn btn-quiet restart" onClick={restart}>
              Recomeçar análise
            </button>
          )}
        </aside>
      </div>
    </div>
  );
}
