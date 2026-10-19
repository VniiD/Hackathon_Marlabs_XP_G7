import { useState } from "react";

import { api, type Meeting, type UserRole } from "../api";
import { errorText, firstName, formatDay, formatSlot, formatTime } from "../lib";

export interface Viewer {
  id: number;
  role: UserRole;
}

/** Reunião pendente que o próprio usuário precisa confirmar (quem pediu não confirma). */
export const needsMyConfirmation = (m: Meeting, role: UserRole) =>
  m.status === "PENDING" && m.initiated_by !== role;

export const isUpcoming = (m: Meeting) =>
  m.status !== "CANCELLED" && new Date(m.slot.end).getTime() >= Date.now();

interface RowProps {
  meeting: Meeting;
  viewer: Viewer;
  name: string;
  showDay: boolean;
  onOpenClient?: (clientId: number) => void;
  onConfirmed: (meeting: Meeting) => void;
}

function MeetingRow({ meeting, viewer, name, showDay, onOpenClient, onConfirmed }: RowProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mine = needsMyConfirmation(meeting, viewer.role);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      onConfirmed(await api.confirmMeeting(meeting.id, viewer));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  const topic = meeting.topic || "Sem pauta definida";
  // Só a assessoria vê o que o cliente contou no chat; o cliente já sabe o que respondeu.
  const heardFromClient = viewer.role === "ADVISOR" ? meeting.context?.answers[0]?.answer : undefined;
  const content = (
    <>
      {!showDay && <span className="line-time">{formatTime(meeting.slot.start)}</span>}
      <span className="line-body">
        <strong>{name}</strong>
        <span className="muted">{showDay ? `${formatSlot(meeting.slot.start)}. ${topic}` : topic}</span>
        {heardFromClient && <span className="muted small">Cliente contou no chat: {heardFromClient}</span>}
      </span>
    </>
  );

  return (
    <li>
      <div className="meeting-row">
        {onOpenClient ? (
          <button type="button" className="line" onClick={() => onOpenClient(meeting.client_id)}>
            {content}
          </button>
        ) : (
          <div className="line is-static">{content}</div>
        )}
        {mine ? (
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={busy}
            aria-label={`Confirmar reunião com ${name}`}
            onClick={confirm}
          >
            {busy ? "Confirmando…" : "Confirmar"}
          </button>
        ) : meeting.status === "CONFIRMED" ? (
          <span className="tag tag-accent">Confirmada</span>
        ) : meeting.status === "DONE" ? (
          <span className="tag">Realizada</span>
        ) : (
          <span className="tag">Aguardando {firstName(name)}</span>
        )}
      </div>
      {error && (
        <p className="state-error small" role="alert">
          Não foi possível confirmar a reunião. {error}
        </p>
      )}
    </li>
  );
}

interface Props {
  meetings: Meeting[];
  viewer: Viewer;
  /** Nome da outra parte da reunião. */
  nameOf: (meeting: Meeting) => string;
  onOpenClient?: (clientId: number) => void;
  empty?: string;
}

/**
 * Agenda de quem está logado: primeiro o que ele precisa confirmar, depois as demais
 * reuniões por dia. Confirmar atualiza a lista na hora, sem recarregar a tela.
 */
export function MeetingAgenda({
  meetings: initial,
  viewer,
  nameOf,
  onOpenClient,
  empty = "Nenhuma reunião marcada.",
}: Props) {
  const [meetings, setMeetings] = useState(initial);
  const upcoming = meetings
    .filter(isUpcoming)
    .sort((a, b) => a.slot.start.localeCompare(b.slot.start));
  const awaiting = upcoming.filter((m) => needsMyConfirmation(m, viewer.role));
  const rest = upcoming.filter((m) => !needsMyConfirmation(m, viewer.role));
  const days = [...new Set(rest.map((m) => formatDay(m.slot.start)))];

  const confirmed = (updated: Meeting) =>
    setMeetings((all) => all.map((m) => (m.id === updated.id ? updated : m)));

  const row = (m: Meeting, showDay: boolean) => (
    <MeetingRow
      key={m.id}
      meeting={m}
      viewer={viewer}
      name={nameOf(m)}
      showDay={showDay}
      onOpenClient={onOpenClient}
      onConfirmed={confirmed}
    />
  );

  if (upcoming.length === 0) return <p className="empty">{empty}</p>;

  return (
    <>
      {awaiting.length > 0 && (
        <div className="agenda-day agenda-awaiting">
          <h3>Aguardando sua confirmação</h3>
          <ul className="plain">{awaiting.map((m) => row(m, true))}</ul>
        </div>
      )}
      {days.map((day) => (
        <div key={day} className="agenda-day">
          <h3>{day}</h3>
          <ul className="plain">
            {rest.filter((m) => formatDay(m.slot.start) === day).map((m) => row(m, false))}
          </ul>
        </div>
      ))}
    </>
  );
}
