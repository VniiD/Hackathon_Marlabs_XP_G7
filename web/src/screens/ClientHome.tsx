import { useState } from "react";

import { api, type ChangeKind, type LoginProfile } from "../api";
import { PortfolioView, loadPortfolio } from "../components/Portfolio";
import { MeetingAgenda } from "../components/MeetingAgenda";
import { Avatar, Load, RiskTag } from "../components/ui";
import { RISK_HINT, errorText, firstName, useAsync } from "../lib";
import { QUESTIONS } from "../questions";

const KINDS: { kind: ChangeKind; label: string }[] = [
  { kind: "APORTE", label: "Aportar" },
  { kind: "RESGATE", label: "Resgatar" },
  { kind: "REBALANCEAMENTO", label: "Rebalancear" },
];

function ChangeRequestForm({ clientId, advisorName }: { clientId: number; advisorName: string }) {
  const [kind, setKind] = useState<ChangeKind>("APORTE");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.requestChange({ client_id: clientId, kind, message: message.trim() });
      setSent(true);
      setMessage("");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={submit}>
      <h2>Pedir alteração na carteira</h2>
      <div className="segmented" role="group" aria-label="Tipo de pedido">
        {KINDS.map((k) => (
          <button
            key={k.kind}
            type="button"
            className={kind === k.kind ? "is-active" : ""}
            aria-pressed={kind === k.kind}
            onClick={() => setKind(k.kind)}
          >
            {k.label}
          </button>
        ))}
      </div>
      <label>
        O que você quer mudar?
        <textarea
          rows={3}
          value={message}
          onChange={(e) => {
            setMessage(e.target.value);
            setSent(false);
          }}
          placeholder="Ex.: quero aportar R$ 5.000 este mês"
          required
        />
      </label>
      <button className="btn btn-primary" type="submit" disabled={busy || !message.trim()}>
        {busy ? "Enviando pedido…" : "Enviar pedido"}
      </button>
      {sent && (
        <p className="ok" role="status">
          Pedido enviado. {firstName(advisorName)} recebeu um alerta no painel.
        </p>
      )}
      {error && (
        <p className="state-error" role="alert">
          O pedido não foi enviado. Tente novamente.
        </p>
      )}
    </form>
  );
}

async function loadHome(clientId: number) {
  const [client, data, suit, profiles] = await Promise.all([
    api.getClient(clientId),
    loadPortfolio(clientId),
    api.getSuitability(clientId),
    api.listProfiles(),
  ]);
  const advisor = profiles.find((p) => p.role === "ADVISOR" && p.id === client.advisor_id);
  return { client, ...data, suit, advisorName: advisor?.name ?? "Sua assessoria" };
}

interface Props {
  profile: LoginProfile;
  onOpenProfile: () => void;
  onOpenChat: () => void;
}

export function ClientHome({ profile, onOpenProfile, onOpenChat }: Props) {
  const home = useAsync(() => loadHome(profile.id), [profile.id]);

  return (
    <Load state={home} label="sua carteira">
      {({ client, portfolio, quotes, suit, advisorName }) => {
        const missing = QUESTIONS.length - suit.answers.length;
        return (
          <>
            <header className="page-head">
              <h1>Olá, {firstName(client.user.name)}</h1>
              <p className="muted">
                <RiskTag profile={client.risk_profile} /> {RISK_HINT[client.risk_profile]}
              </p>
            </header>

            {missing > 0 && (
              <div className="notice">
                <p>
                  <strong>Conte mais sobre você.</strong> Faltam {missing}{" "}
                  {missing === 1 ? "pergunta" : "perguntas"} da análise de perfil. Quanto mais sua
                  assessoria souber, melhores as recomendações.
                </p>
                <button type="button" className="btn" onClick={onOpenProfile}>
                  Continuar análise
                </button>
              </div>
            )}

            <div className="cols">
              <PortfolioView portfolio={portfolio} quotes={quotes} title="Seu patrimônio" />

              <div className="stack">
                <section className="panel">
                  <h2>Sua assessoria</h2>
                  <p className="person">
                    <Avatar name={advisorName} />
                    <span>{advisorName}</span>
                  </p>
                  <NextMeeting clientId={profile.id} advisorName={advisorName} />
                  <h3>Marcar reunião de 30 minutos</h3>
                  <p className="muted">
                    Peça pelo chat: o copiloto pergunta o que você quer tratar para{" "}
                    {firstName(advisorName)} chegar preparada e já escolhe o horário com você.
                  </p>
                  <button type="button" className="btn btn-primary" onClick={onOpenChat}>
                    Marcar pelo chat
                  </button>
                </section>

                <ChangeRequestForm clientId={profile.id} advisorName={advisorName} />
              </div>
            </div>
          </>
        );
      }}
    </Load>
  );
}

function NextMeeting(props: { clientId: number; advisorName: string }) {
  const meetings = useAsync(() => api.getClientMeetings(props.clientId), [props.clientId]);
  if (meetings.status !== "ready") return null;
  return (
    <MeetingAgenda
      meetings={meetings.data}
      viewer={{ id: props.clientId, role: "CLIENT" }}
      nameOf={() => props.advisorName}
    />
  );
}
