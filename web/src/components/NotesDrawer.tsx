import { useEffect, useRef, useState } from "react";

import { api, type AdvisorNote } from "../api";
import { errorText, formatDate } from "../lib";
import { Icon } from "./ui";

const MAX_LENGTH = 500;

interface NoteCardProps {
  note: AdvisorNote;
  onChanged: (note: AdvisorNote) => void;
  onDeleted: (id: number) => void;
  onError: (message: string) => void;
}

function NoteCard({ note, onChanged, onDeleted, onError }: NoteCardProps) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(note.text);
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<void>, failure: string) {
    setBusy(true);
    try {
      await action();
    } catch (e) {
      onError(`${failure} (${errorText(e)})`);
    } finally {
      setBusy(false);
    }
  }

  const save = () =>
    run(async () => {
      onChanged(await api.editNote(note.id, text.trim()));
      setEditing(false);
    }, "A anotação não foi alterada.");

  const remove = () =>
    run(async () => {
      await api.deleteNote(note.id);
      onDeleted(note.id);
    }, "A anotação não foi apagada.");

  if (editing) {
    return (
      <li className="note is-editing">
        <textarea
          aria-label="Editar anotação"
          rows={3}
          maxLength={MAX_LENGTH}
          value={text}
          autoFocus
          onChange={(e) => setText(e.target.value)}
        />
        <div className="note-actions">
          <button type="button" className="btn btn-primary" disabled={busy || !text.trim()} onClick={save}>
            Salvar
          </button>
          <button
            type="button"
            className="btn btn-quiet"
            disabled={busy}
            onClick={() => {
              setText(note.text);
              setEditing(false);
            }}
          >
            Cancelar
          </button>
        </div>
      </li>
    );
  }

  return (
    <li className="note">
      <p>{note.text}</p>
      <div className="note-foot">
        <time dateTime={note.created_at}>{formatDate(note.created_at)}</time>
        <button
          type="button"
          className="note-tool"
          aria-label="Editar anotação"
          title="Editar"
          disabled={busy}
          onClick={() => setEditing(true)}
        >
          <Icon name="edit" size={16} />
        </button>
        <button
          type="button"
          className="note-tool"
          aria-label="Apagar anotação"
          title="Apagar"
          disabled={busy}
          onClick={remove}
        >
          <Icon name="trash" size={16} />
        </button>
      </div>
    </li>
  );
}

/** Bloco de notas do assessor: fica recolhido numa aba na borda direita da tela. */
export function NotesDrawer({ advisorId, clientId }: { advisorId: number; clientId: number }) {
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState<AdvisorNote[] | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api
      .getNotes(clientId)
      .then(setNotes)
      .catch((e) => setError(`As anotações não carregaram. (${errorText(e)})`));
  }, [clientId]);

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  async function add() {
    const text = draft.trim();
    if (!text || busy) return;
    setBusy(true);
    setError(null);
    try {
      const note = await api.addNote(clientId, advisorId, text);
      setNotes((list) => [note, ...(list ?? [])]);
      setDraft("");
    } catch (e) {
      setError(`A anotação não foi salva. (${errorText(e)})`);
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        className="notes-tab"
        aria-expanded="false"
        onClick={() => setOpen(true)}
      >
        <Icon name="note" size={16} />
        <span>Contexto pessoal</span>
      </button>
    );
  }

  return (
    <>
      <div className="notes-backdrop" onClick={() => setOpen(false)} />
      <aside className="notes" aria-label="Contexto pessoal">
        <header className="notes-head">
          <div>
            <h2>Contexto pessoal</h2>
            <p className="muted small">Só você vê. O cliente não tem acesso.</p>
          </div>
          <button
            type="button"
            className="note-tool"
            aria-label="Fechar contexto pessoal"
            onClick={() => setOpen(false)}
          >
            <Icon name="close" />
          </button>
        </header>

        <form
          className="notes-new"
          onSubmit={(e) => {
            e.preventDefault();
            add();
          }}
        >
          <textarea
            ref={inputRef}
            aria-label="Nova anotação"
            rows={2}
            maxLength={MAX_LENGTH}
            placeholder="Ex.: gosta de acampar"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              // Enter anota; Shift+Enter quebra a linha.
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                add();
              }
            }}
          />
          <button type="submit" className="btn btn-primary" disabled={busy || !draft.trim()}>
            Anotar
          </button>
        </form>

        {error && (
          <p className="state-error small" role="alert">
            {error}
          </p>
        )}
        {notes === null && !error && <p className="muted small">Carregando anotações…</p>}
        {notes?.length === 0 && (
          <p className="muted small">
            Nenhuma anotação ainda. Registre aqui o que ajuda a puxar assunto na próxima conversa.
          </p>
        )}

        <ul className="note-list">
          {notes?.map((note) => (
            <NoteCard
              key={note.id}
              note={note}
              onChanged={(changed) =>
                setNotes((list) => list?.map((n) => (n.id === changed.id ? changed : n)) ?? null)
              }
              onDeleted={(id) => setNotes((list) => list?.filter((n) => n.id !== id) ?? null)}
              onError={setError}
            />
          ))}
        </ul>
      </aside>
    </>
  );
}
