import { useState } from "react";

import {
  api,
  type AdvisorOverview,
  type ChangeRequest,
  type ClientProfile,
  type CurrencyRate,
  type LoginProfile,
  type Meeting,
  type NewsImpact,
  type PrioritizedClient,
  type RiskProfile,
} from "../api";
import { AllocationStrip, Avatar, Icon, Load, RiskTag, type Part } from "../components/ui";
import {
  ASSET_COLOR,
  ASSET_LABEL,
  CASH_COLOR,
  RISK_LABEL,
  firstName,
  formatAgo,
  formatBRL,
  formatBRLShort,
  formatDay,
  formatPct,
  formatShare,
  formatTime,
  usePollingAsync,
} from "../lib";

export interface ClientRow extends PrioritizedClient {
  client: ClientProfile;
}

export const KIND_LABEL: Record<ChangeRequest["kind"], string> = {
  APORTE: "Aporte",
  RESGATE: "Resgate",
  REBALANCEAMENTO: "Rebalanceamento",
};

export const SENTIMENT_LABEL: Record<NewsImpact["sentiment"], string> = {
  NEGATIVE: "Negativa",
  POSITIVE: "Positiva",
  NEUTRAL: "Neutra",
};

export async function loadRows(advisorId: number): Promise<ClientRow[]> {
  const priorities = await api.getPriorities(advisorId);
  const clients = await Promise.all(priorities.map((p) => api.getClient(p.client_id)));
  return priorities
    .map((p, i) => ({ ...p, client: clients[i] }))
    .sort((a, b) => b.criticality_score - a.criticality_score);
}

const VISIBLE_HOLDINGS = 6;

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? "Bom dia" : hour < 18 ? "Boa tarde" : "Boa noite";
}

function CurrencyRow({ rates }: { rates: CurrencyRate[] }) {
  if (!rates.length) return null;

  return (
    <section className="panel">
      <h2>Moedas e câmbio</h2>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
        {rates.map((rate) => {
          const value = Number(rate.value);
          const variation = Number(rate.variation_pct);
          return (
            <div
              key={rate.code}
              style={{
                minWidth: "120px",
                padding: "0.75rem 0.9rem",
                borderRadius: "12px",
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.08)",
              }}
            >
              <div className="muted small" style={{ marginBottom: "0.25rem" }}>{rate.code}</div>
              <strong style={{ display: "block", fontSize: "1.05rem" }}>{value.toFixed(2)}</strong>
              <span
                className="muted small"
                style={{ color: variation >= 0 ? "#7fe0a1" : "#ff8e8e" }}
              >
                {formatPct(rate.variation_pct)}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Panorama({ overview }: { overview: AdvisorOverview }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  const parts: Part[] = overview.by_asset_class.map((a) => ({
    key: a.asset_class,
    label: ASSET_LABEL[a.asset_class],
    value: Number(a.total_value),
    color: ASSET_COLOR[a.asset_class],
  }));
  const cash = Number(overview.external_cash);
  if (cash > 0) parts.push({ key: "CASH", label: "Saldo em conta", value: cash, color: CASH_COLOR });

  const holdings = overview.holdings.filter((h) => !selected || h.asset_class === selected);
  const visible = showAll ? holdings : holdings.slice(0, VISIBLE_HOLDINGS);

  return (
    <section className="panel panel-hero">
      <header className="panel-head">
        <h2>Patrimônio sob assessoria</h2>
        <p className="figure figure-lg">{formatBRL(overview.total_aum)}</p>
        <p className="muted">
          {overview.clients_count} clientes. {formatBRLShort(overview.external_aum)} estão em outras
          instituições, visíveis pelo Open Finance.
        </p>
      </header>

      <AllocationStrip parts={parts} selected={selected} onSelect={setSelected} size="lg" />

      <div className="sub-head">
        <h3>
          {selected === "CASH"
            ? "Saldo em conta"
            : selected
              ? `Ativos de ${ASSET_LABEL[selected as keyof typeof ASSET_LABEL].toLowerCase()}`
              : "Ativos nas carteiras"}
        </h3>
        {selected && (
          <button type="button" className="btn btn-quiet" onClick={() => setSelected(null)}>
            Ver todas as classes
          </button>
        )}
      </div>

      {holdings.length === 0 ? (
        <p className="empty">
          Saldo parado em contas de outras instituições, sem ativo associado.
        </p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Ativo</th>
                <th className="col-opt">Classe</th>
                <th className="num col-opt">Clientes</th>
                <th className="num">Do total</th>
                <th className="num">Valor</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((h) => (
                <tr key={h.ticker}>
                  <td>
                    <span className="swatch" style={{ background: ASSET_COLOR[h.asset_class] }} />
                    {h.ticker}
                  </td>
                  <td className="muted col-opt">{ASSET_LABEL[h.asset_class]}</td>
                  <td className="num col-opt">{h.clients_count}</td>
                  <td className="num">{formatShare(h.share_pct)}</td>
                  <td className="num">{formatBRL(h.total_value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {holdings.length > VISIBLE_HOLDINGS && (
        <button type="button" className="btn btn-quiet more" onClick={() => setShowAll((v) => !v)}>
          {showAll ? "Mostrar só os maiores" : `Ver os ${holdings.length} ativos`}
        </button>
      )}
    </section>
  );
}

interface AgendaProps {
  meetings: Meeting[];
  names: Map<number, string>;
  onOpenClient: (id: number) => void;
}

function Agenda({ meetings, names, onOpenClient }: AgendaProps) {
  const days = [...new Set(meetings.map((m) => formatDay(m.slot.start)))];
  return (
    <section className="panel">
      <h2>Próximas reuniões</h2>
      {meetings.length === 0 && <p className="empty">Nenhuma reunião marcada.</p>}
      {days.map((day) => (
        <div key={day} className="agenda-day">
          <h3>{day}</h3>
          <ul className="plain">
            {meetings
              .filter((m) => formatDay(m.slot.start) === day)
              .map((m) => (
                <li key={m.id}>
                  <button type="button" className="line" onClick={() => onOpenClient(m.client_id)}>
                    <span className="line-time">{formatTime(m.slot.start)}</span>
                    <span className="line-body">
                      <strong>{names.get(m.client_id) ?? "Cliente"}</strong>
                      <span className="muted">{m.topic || "Sem pauta definida"}</span>
                    </span>
                  </button>
                </li>
              ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

function Requests({ requests, names, onOpenClient }: { requests: ChangeRequest[] } & Omit<AgendaProps, "meetings">) {
  return (
    <section className="panel">
      <h2>Pedidos dos clientes</h2>
      {requests.length === 0 ? (
        <p className="empty">Nenhum pedido em aberto.</p>
      ) : (
        <ul className="plain">
          {requests.map((r) => (
            <li key={r.id}>
              <button type="button" className="line" onClick={() => onOpenClient(r.client_id)}>
                <span className="line-body">
                  <strong>
                    {names.get(r.client_id) ?? "Cliente"} <span className="tag">{KIND_LABEL[r.kind]}</span>
                  </strong>
                  <span className="muted">{r.message}</span>
                  <span className="muted small">{formatAgo(r.created_at)}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function NewsList({ news, onOpenClient }: { news: NewsImpact[]; onOpenClient?: (id: number) => void }) {
  if (news.length === 0) return <p className="empty">Nenhuma notícia recente afeta estas carteiras.</p>;
  return (
    <div className="news-viewport" aria-label="Notícias recentes; role para ver mais">
      <ul className="news">
        {news.map((item) => {
          const related = new Map<number, { name: string; reasons: string[] }>();
          for (const client of item.affected_clients) {
            related.set(client.client_id, {
              name: client.client_name,
              reasons: [`Carteira ${formatShare(client.exposure_pct)}`],
            });
          }
          for (const client of item.interested_clients) {
            const entry = related.get(client.client_id) ?? {
              name: client.client_name,
              reasons: [],
            };
            entry.reasons.push(`Interesse: ${client.matched_interest}`);
            related.set(client.client_id, entry);
          }

          return (
            <li key={item.id}>
              <p className="news-meta">
                <span className={`mood mood-${item.sentiment.toLowerCase()}`}>
                  <span className="mood-mark" aria-hidden="true" />
                  {SENTIMENT_LABEL[item.sentiment]}
                </span>
                <span className="muted">
                  {item.source}, {formatAgo(item.published_at)}
                </span>
              </p>
              <h3 className="news-headline">
                {item.url ? (
                  <a href={item.url} target="_blank" rel="noreferrer">
                    {item.title}
                  </a>
                ) : item.title}
              </h3>
              <p className="muted news-summary">{item.summary}</p>
              <div className="news-related">
                <span className="news-related-label">
                  {related.size ? "Vinculada a:" : "Sem vínculo com clientes"}
                </span>
                {related.size > 0 && (
                  <div className="news-related-items">
                    {[...related].map(([clientId, client]) => {
                      const label = `${client.name} · ${client.reasons.join(" · ")}`;
                      return onOpenClient ? (
                        <button
                          key={clientId}
                          type="button"
                          className="news-client-chip"
                          title={label}
                          onClick={() => onOpenClient(clientId)}
                        >
                          <strong>{client.name}</strong>
                          <span>{client.reasons.join(" · ")}</span>
                        </button>
                      ) : (
                        <span key={clientId} className="news-client-chip" title={label}>
                          <strong>{client.name}</strong>
                          <span>{client.reasons.join(" · ")}</span>
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

interface ClientsProps {
  rows: ClientRow[];
  overview: AdvisorOverview;
  newsSentiments: Map<number, NewsImpact["sentiment"][]>;
  onOpenClient: (id: number) => void;
}

function Clients({ rows, overview, newsSentiments, onOpenClient }: ClientsProps) {
  const [filter, setFilter] = useState<RiskProfile | null>(null);
  const visible = rows.filter((r) => !filter || r.client.risk_profile === filter);
  const clientFlag = (clientId: number, score: number) => {
    if (score >= 10) return "ATTENTION" as const;
    const sentiments = newsSentiments.get(clientId) ?? [];
    if (sentiments.includes("NEGATIVE")) return "NEGATIVE" as const;
    if (sentiments.includes("POSITIVE")) return "POSITIVE" as const;
    return "NEUTRAL" as const;
  };

  return (
    <section className="panel">
      <h2>Clientes</h2>
      <div className="segments" role="group" aria-label="Filtrar por perfil">
        {overview.segments.map((s) => (
          <button
            key={s.risk_profile}
            type="button"
            className={filter === s.risk_profile ? "segment is-active" : "segment"}
            aria-pressed={filter === s.risk_profile}
            onClick={() => setFilter(filter === s.risk_profile ? null : s.risk_profile)}
          >
            <span className="segment-label">{RISK_LABEL[s.risk_profile]}</span>
            <span className="segment-count">{s.clients_count}</span>
            <span className="muted small">
              {formatShare(s.aum_share_pct)} do patrimônio
            </span>
          </button>
        ))}
      </div>

      <p className="muted small list-caption">
        {filter
          ? `Perfil ${RISK_LABEL[filter].toLowerCase()}, do mais ao menos crítico hoje`
          : "Do mais ao menos crítico hoje"}
      </p>
      {visible.length === 0 && <p className="empty">Nenhum cliente com este perfil.</p>}
      <ul className="plain">
        {visible.map((r) => (
          <li key={r.client_id}>
            <button type="button" className="line" onClick={() => onOpenClient(r.client_id)}>
              <Avatar name={r.client.user.name} />
              <span className="line-body">
                <strong>
                  {r.client.user.name} <RiskTag profile={r.client.risk_profile} />
                </strong>
                <span className="muted">{r.next_best_action.title}</span>
              </span>
              {(() => {
                const flag = clientFlag(r.client_id, r.criticality_score);
                const label = flag === "ATTENTION" ? "Atenção" : SENTIMENT_LABEL[flag];
                return (
                  <span
                    className={`mood mood-${flag.toLowerCase()} client-flag`}
                    aria-label={`Status do cliente: ${label}`}
                  >
                    <span className="mood-mark" aria-hidden="true" />
                    {label}
                  </span>
                );
              })()}
              <Icon name="chevron" size={16} />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

async function loadDashboard(advisorId: number) {
  const [overview, rows, news, meetings, requests, currencyLine] = await Promise.all([
    api.getOverview(advisorId),
    loadRows(advisorId),
    api.getNews(advisorId),
    api.getMeetings(advisorId),
    api.getChangeRequests(advisorId),
    api.getCurrencyLine(),
  ]);
  return {
    overview,
    rows,
    news,
    meetings,
    requests,
    currencyLine,
    updatedAt: new Date().toISOString(),
  };
}

interface Props {
  advisor: LoginProfile;
  onOpenClient: (clientId: number) => void;
}

export function AdvisorHome({ advisor, onOpenClient }: Props) {
  const state = usePollingAsync(() => loadDashboard(advisor.id), [advisor.id]);

  return (
    <Load state={state} label="o painel">
      {({ overview, rows, news, meetings, requests, currencyLine, updatedAt }) => {
        const names = new Map(rows.map((r) => [r.client_id, r.client.user.name]));
        const needsReview = rows.filter((r) => r.criticality_score >= 10).length;
        const sentimentsByClient = new Map<number, Set<NewsImpact["sentiment"]>>();
        for (const item of news) {
          const relatedIds = new Set([
            ...item.affected_clients.map((client) => client.client_id),
            ...item.interested_clients.map((client) => client.client_id),
          ]);
          for (const clientId of relatedIds) {
            const sentiments = sentimentsByClient.get(clientId) ?? new Set();
            sentiments.add(item.sentiment);
            sentimentsByClient.set(clientId, sentiments);
          }
        }
        const newsSentiments = new Map(
          [...sentimentsByClient].map(([clientId, sentiments]) => [
            clientId,
            (["NEGATIVE", "POSITIVE", "NEUTRAL"] as const).filter((sentiment) =>
              sentiments.has(sentiment),
            ),
          ]),
        );
        return (
          <>
            <header className="page-head">
              <h1>
                {greeting()}, {firstName(advisor.name)}
              </h1>
              <p className="muted">
                {needsReview === 0
                  ? "Nenhum cliente precisa de revisão prioritária hoje."
                  : needsReview === 1
                    ? "1 cliente requer revisão hoje."
                    : `${needsReview} clientes requerem revisão hoje.`}{" "}
                {meetings.length} {meetings.length === 1 ? "reunião marcada" : "reuniões marcadas"} e{" "}
                {requests.length} {requests.length === 1 ? "pedido em aberto" : "pedidos em aberto"}.
              </p>
              <p className="muted small">
                Dados consultados às {formatTime(updatedAt)}. Notícias e prioridades atualizam a cada minuto; câmbio usa referência diária e é reconsultado a cada 5 minutos.
              </p>
            </header>

            <div className="cols">
              <div className="stack">
                <Panorama overview={overview} />
                <CurrencyRow rates={currencyLine} />
                <Clients
                  rows={rows}
                  overview={overview}
                  newsSentiments={newsSentiments}
                  onOpenClient={onOpenClient}
                />
              </div>
              <div className="stack">
                <Agenda meetings={meetings} names={names} onOpenClient={onOpenClient} />
                <Requests requests={requests} names={names} onOpenClient={onOpenClient} />
                <section className="panel">
                  <h2>Notícias ligadas a ativos e interesses</h2>
                  <NewsList news={news} onOpenClient={onOpenClient} />
                </section>
              </div>
            </div>
          </>
        );
      }}
    </Load>
  );
}
