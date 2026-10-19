import { useState } from "react";

import { api, type Meeting, type TimeSlot, type UserRole } from "../api";
import { errorText, formatDay, formatSlot, formatTime, useAsync } from "../lib";

interface Props {
  advisorId: number;
  clientId: number;
  topic: string;
  /** Quem está pedindo; a outra parte é quem confirma. */
  initiatedBy: UserRole;
  onScheduled?: (meeting: Meeting) => void;
}

/** Horários livres do assessor; um clique marca a reunião de 30 minutos. */
export function SlotPicker({ advisorId, clientId, topic, initiatedBy, onScheduled }: Props) {
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [done, setDone] = useState<Meeting | null>(null);
  const [error, setError] = useState<string | null>(null);
  const slots = useAsync(() => api.getFreeSlots(advisorId), [advisorId, version]);

  async function book(slot: TimeSlot) {
    setBusy(slot.start);
    setError(null);
    try {
      const meeting = await api.scheduleMeeting({
        client_id: clientId,
        advisor_id: advisorId,
        topic,
        preferred: slot,
        initiated_by: initiatedBy,
      });
      setDone(meeting);
      setVersion((v) => v + 1);
      onScheduled?.(meeting);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="slots">
      {slots.status === "loading" && <p className="muted">Buscando horários livres…</p>}
      {slots.status === "error" && (
        <p className="state-error" role="alert">
          Não foi possível buscar os horários. Tente novamente.
        </p>
      )}
      {slots.status === "ready" && slots.data.length === 0 && (
        <p className="muted">Sem horários livres nos próximos dias.</p>
      )}
      {slots.status === "ready" && slots.data.length > 0 && (
        <ul className="slot-list">
          {slots.data.map((s) => (
            <li key={s.start}>
              <button
                type="button"
                className="slot"
                disabled={busy !== null}
                aria-busy={busy === s.start}
                onClick={() => book(s)}
              >
                <span className="slot-day">{formatDay(s.start)}</span>
                <span className="slot-time">{formatTime(s.start)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {done && (
        <p className="ok" role="status">
          Reunião pedida para {formatSlot(done.slot.start)}. Ela vale quando{" "}
          {initiatedBy === "CLIENT" ? "sua assessoria" : "o cliente"} confirmar.
        </p>
      )}
      {error && (
        <p className="state-error" role="alert">
          Não foi possível marcar a reunião. Tente outro horário.
        </p>
      )}
    </div>
  );
}
