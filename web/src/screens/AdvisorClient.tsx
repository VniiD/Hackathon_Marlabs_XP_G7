import { useState } from "react";

import { api, type SuitabilityAnswer } from "../api";
import { PortfolioView, loadPortfolio } from "../components/Portfolio";
import { MeetingAgenda, isUpcoming } from "../components/MeetingAgenda";
import { MeetingBriefingPanel } from "../components/MeetingBriefing";
import { NotesDrawer } from "../components/NotesDrawer";
import { SlotPicker } from "../components/SlotPicker";
import { Avatar, Icon, Load, RiskTag, Severity } from "../components/ui";
import { formatAgo, useAsync } from "../lib";
import { QUESTIONS, coveredTopics } from "../questions";
import { KIND_LABEL, NewsList, loadRows } from "./AdvisorHome";

async function loadClient(advisorId: number, clientId: number) {
  const [rows, data, news, meetings, requests, suit] = await Promise.all([
    loadRows(advisorId),
    loadPortfolio(clientId),
    api.getNews(advisorId),
    api.getMeetings(advisorId),
    api.getChangeRequests(advisorId),
    api.getSuitability(clientId),
  ]);
  const row = rows.find((r) => r.client_id === clientId);
  if (!row) throw new Error("Cliente não encontrado na sua carteira");
  return {
    row,
    suit,
    ...data,
    news: news.filter((n) => n.affected_clients.some((c) => c.client_id === clientId)),
    meetings: meetings.filter((m) => m.client_id === clientId),
    requests: requests.filter((r) => r.client_id === clientId),
  };
}

/** O que o cliente contou na análise de perfil, pergunta a pergunta. */
function FinancialLife({ answers }: { answers: SuitabilityAnswer[] }) {
  const byId = new Map(answers.map((a) => [a.question_id, a]));
  const answered = QUESTIONS.filter((q) => byId.has(q.id));
  const pending = QUESTIONS.filter((q) => !byId.has(q.id));

  return (
    <section className="panel">
      <h2>Vida financeira, nas palavras do cliente</h2>
      {answered.length === 0 ? (
        <p className="empty">O cliente ainda não respondeu a análise de perfil.</p>
      ) : (
        <dl className="answers">
          {answered.map((q) => {
            const a = byId.get(q.id)!;
            const covered = coveredTopics(q, a.answer);
            const missing = q.topics.filter((_, i) => !covered[i]);
            return (
              <div key={q.id}>
                <dt>
                  {q.short}
                  {q.quick && a.option_index !== null && (
                    <span className="tag">{q.quick.options[a.option_index]}</span>
                  )}
                </dt>
                <dd>{a.answer || <span className="muted">Sem detalhes além da opção escolhida.</span>}</dd>
                {missing.length > 0 && (
                  <dd className="muted small">
                    Não mencionou: {missing.map((t) => t.label.toLowerCase()).join("; ")}.
                  </dd>
                )}
              </div>
            );
          })}
        </dl>
      )}
      {answered.length > 0 && pending.length > 0 && (
        <p className="muted small">
          Ainda sem resposta: {pending.map((q) => q.short.toLowerCase()).join(", ")}.
        </p>
      )}
    </section>
  );
}

interface Props {
  advisorId: number;
  clientId: number;
  onBack: () => void;
}

export function AdvisorClient({ advisorId, clientId, onBack }: Props) {
  const [version, setVersion] = useState(0);
  const state = useAsync(() => loadClient(advisorId, clientId), [advisorId, clientId, version]);

  return (
    <>
      <button type="button" className="btn btn-quiet back" onClick={onBack}>
        <Icon name="back" size={16} /> Painel
      </button>

      <NotesDrawer advisorId={advisorId} clientId={clientId} />

      <Load state={state} label="o cliente">
        {({ row, suit, portfolio, quotes, news, meetings, requests }) => {
          const { client, next_best_action: nba } = row;
          // A próxima reunião que o cliente marcou pelo chat já chega com o que ele contou.
          const briefed = meetings
            .filter((m) => isUpcoming(m) && m.context)
            .sort((a, b) => a.slot.start.localeCompare(b.slot.start))[0];
          return (
            <>
              <header className="client-head">
                <Avatar name={client.user.name} size="xl" />
                <div>
                  <h1>{client.user.name}</h1>
                  <p className="muted">
                    <RiskTag profile={client.risk_profile} /> {client.user.email}
                  </p>
                </div>
                <div className="client-score" title="Criticidade de 0 a 100">
                  <Severity score={row.criticality_score} showScore />
                </div>
              </header>

              <section className="nba">
                <div>
                  <p className="muted small">Próxima melhor ação</p>
                  <h2>{nba.title}</h2>
                  <p>{nba.rationale}</p>
                </div>
                <div>
                  <h3>Marcar reunião de 30 minutos</h3>
                  <SlotPicker
                    advisorId={advisorId}
                    clientId={clientId}
                    topic={nba.title}
                    initiatedBy="ADVISOR"
                    onScheduled={() => setVersion((v) => v + 1)}
                  />
                </div>
              </section>

              {briefed && <MeetingBriefingPanel advisorId={advisorId} meetingId={briefed.id} />}

              <div className="cols">
                <div className="stack">
                  <PortfolioView portfolio={portfolio} quotes={quotes} title="Patrimônio unificado" />
                  <FinancialLife answers={suit.answers} />
                </div>

                <div className="stack">
                  <section className="panel">
                    <h2>Reuniões e pedidos</h2>
                    {meetings.length === 0 && requests.length === 0 && (
                      <p className="empty">Nenhuma reunião marcada nem pedido em aberto.</p>
                    )}
                    {meetings.length > 0 && (
                      <MeetingAgenda
                        meetings={meetings}
                        viewer={{ id: advisorId, role: "ADVISOR" }}
                        nameOf={() => client.user.name}
                      />
                    )}
                    <ul className="plain">
                      {requests.map((r) => (
                        <li key={`r${r.id}`}>
                          <strong>
                            <span className="tag">{KIND_LABEL[r.kind]}</span> {formatAgo(r.created_at)}
                          </strong>
                          <span className="muted">{r.message}</span>
                        </li>
                      ))}
                    </ul>
                  </section>

                  <section className="panel">
                    <h2>Notícias que afetam esta carteira</h2>
                    <NewsList news={news} />
                  </section>
                </div>
              </div>
            </>
          );
        }}
      </Load>
    </>
  );
}
