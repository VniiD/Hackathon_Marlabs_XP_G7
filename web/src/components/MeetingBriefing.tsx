import { api, type BriefingNews, type MeetingBriefing } from "../api";
import { ASSET_LABEL, formatAgo, formatBRL, formatShare, formatSlot, useAsync } from "../lib";
import { Load } from "./ui";

const SENTIMENT_LABEL: Record<BriefingNews["sentiment"], string> = {
  NEGATIVE: "Negativa",
  POSITIVE: "Positiva",
  NEUTRAL: "Neutra",
};

function Briefing({ briefing }: { briefing: MeetingBriefing }) {
  const { context, portfolio, news, talking_points } = briefing;
  return (
    <>
      <p className="muted">
        {formatSlot(briefing.meeting.slot.start)}. {briefing.meeting.topic || "Sem pauta definida"}
      </p>

      <div className="cols">
        <div className="stack">
          <h3>O que o cliente contou antes de marcar</h3>
          {context ? (
            <dl className="answers">
              {context.answers.map((a) => (
                <div key={a.key}>
                  <dt>{a.question}</dt>
                  <dd>{a.answer}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="empty">Reunião sem perguntas respondidas no chat.</p>
          )}

          {talking_points.length > 0 && (
            <>
              <h3>Pontos de conversa</h3>
              <ul className="plain">
                {talking_points.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </>
          )}
        </div>

        <div className="stack">
          <h3>Carteira hoje</h3>
          <p className="figure">{formatBRL(portfolio.total_net_worth)}</p>
          <ul className="plain">
            {portfolio.allocation.map((a) => (
              <li key={a.asset_class}>
                <strong>{ASSET_LABEL[a.asset_class]}</strong>
                <span className="muted">
                  {formatShare(a.share_pct)}, {formatBRL(a.value)}
                </span>
              </li>
            ))}
          </ul>

          <h3>Notícias que tocam a carteira</h3>
          {news.length === 0 ? (
            <p className="empty">Nenhuma notícia recente sobre os ativos do cliente.</p>
          ) : (
            <ul className="plain">
              {news.map((n) => (
                <li key={n.title}>
                  <strong>{n.title}</strong>
                  <span className="muted">
                    <span className="tag">{SENTIMENT_LABEL[n.sentiment]}</span> {n.source},{" "}
                    {formatAgo(n.published_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </>
  );
}

/** O que a assessoria precisa para entrar na reunião: contexto do chat, carteira e notícias. */
export function MeetingBriefingPanel({
  advisorId,
  meetingId,
}: {
  advisorId: number;
  meetingId: number;
}) {
  const state = useAsync(() => api.getMeetingBriefing(advisorId, meetingId), [advisorId, meetingId]);
  return (
    <section className="panel briefing">
      <h2>Preparação da reunião</h2>
      <Load state={state} label="o briefing da reunião">
        {(briefing) => <Briefing briefing={briefing} />}
      </Load>
    </section>
  );
}
