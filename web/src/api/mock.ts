import { REQUIRED } from "../questions";
import type {
  AdvisorOverview,
  Api,
  AssetClass,
  ChangeRequest,
  ClientProfile,
  ExternalAccount,
  Holding,
  LoginProfile,
  Meeting,
  NewsImpact,
  PrioritizedClient,
  Quote,
  RiskProfile,
  Suitability,
  TimeSlot,
} from "./types";

const ADVISOR_ID = 1;

const clients: ClientProfile[] = [
  {
    user: { id: 1, name: "Helena Duarte", email: "helena@exemplo.com", role: "CLIENT" },
    advisor_id: ADVISOR_ID,
    risk_profile: "CONSERVADOR",
    context: {
      hobbies: ["Jardinagem", "Viagens"],
      favorite_team: "Palmeiras",
      family_dates: [{ label: "Aniversário do neto", date: "2026-10-18" }],
    },
  },
  {
    user: { id: 2, name: "Rafael Monteiro", email: "rafael@exemplo.com", role: "CLIENT" },
    advisor_id: ADVISOR_ID,
    risk_profile: "ARROJADO",
    context: { hobbies: ["Ciclismo", "Vinhos"], favorite_team: "Flamengo", family_dates: [] },
  },
  {
    user: { id: 3, name: "Beatriz Nogueira", email: "beatriz@exemplo.com", role: "CLIENT" },
    advisor_id: ADVISOR_ID,
    risk_profile: "MODERADO",
    context: {
      hobbies: ["Corrida"],
      favorite_team: null,
      family_dates: [{ label: "Aniversário de casamento", date: "2026-11-02" }],
    },
  },
  {
    user: { id: 4, name: "Otávio Lins", email: "otavio@exemplo.com", role: "CLIENT" },
    advisor_id: ADVISOR_ID,
    risk_profile: "MODERADO",
    context: { hobbies: ["Pesca", "Golfe"], favorite_team: "Grêmio", family_dates: [] },
  },
  {
    user: { id: 5, name: "Camila Prates", email: "camila@exemplo.com", role: "CLIENT" },
    advisor_id: ADVISOR_ID,
    risk_profile: "CONSERVADOR",
    context: { hobbies: ["Leitura"], favorite_team: "Corinthians", family_dates: [] },
  },
  {
    user: { id: 6, name: "Marina Sales", email: "marina@exemplo.com", role: "CLIENT" },
    advisor_id: ADVISOR_ID,
    risk_profile: "MODERADO",
    context: { hobbies: [], favorite_team: null, family_dates: [] },
  },
];

const advisor: LoginProfile = {
  id: ADVISOR_ID,
  name: "Paula Azevedo",
  email: "paula@exemplo.com",
  role: "ADVISOR",
  needs_onboarding: false,
};

// Clientes que ainda não responderam as perguntas obrigatórias.
const pendingOnboarding = new Set<number>([6]);

const priorities: PrioritizedClient[] = [
  {
    client_id: 1,
    criticality_score: 86,
    next_best_action: {
      title: "Ligar para acalmar e revisar exposição",
      rationale: "Carteira caiu 4,2% hoje e o perfil é conservador.",
    },
  },
  {
    client_id: 3,
    criticality_score: 61,
    next_best_action: {
      title: "Propor rebalanceamento",
      rationale: "Exposição a ações acima do alvo do perfil moderado; 41 dias sem contato.",
    },
  },
  {
    client_id: 5,
    criticality_score: 47,
    next_best_action: {
      title: "Apresentar alternativa ao CDB que vence",
      rationale: "R$ 180 mil em renda fixa vencem em 9 dias.",
    },
  },
  {
    client_id: 6,
    criticality_score: 35,
    next_best_action: {
      title: "Confirmar a análise de perfil",
      rationale: "Cliente nova: o perfil de investidora ainda não foi respondido.",
    },
  },
  {
    client_id: 2,
    criticality_score: 28,
    next_best_action: {
      title: "Enviar resumo de mercado",
      rationale: "Notícia positiva para PETR4, maior posição da carteira.",
    },
  },
  {
    client_id: 4,
    criticality_score: 12,
    next_best_action: {
      title: "Contato de acompanhamento",
      rationale: "Rotina de relacionamento.",
    },
  },
];

const h = (
  ticker: string,
  asset_class: Holding["asset_class"],
  quantity: string,
  market_value: string,
  institution = "INTERNAL",
): Holding => ({ ticker, asset_class, quantity, market_value, institution });

const portfolios: Record<number, { internal: Holding[]; external: ExternalAccount[] }> = {
  1: {
    internal: [
      h("TESOURO-SELIC-2029", "RENDA_FIXA", "42", "610000.00"),
      h("ITUB4", "ACOES", "3200", "112640.00"),
      h("KNRI11", "FUNDOS", "900", "141300.00"),
    ],
    external: [
      {
        institution: "Banco Aurora",
        account_id: "AUR-0098",
        balance: "84500.00",
        holdings: [h("CDB-AURORA-2027", "RENDA_FIXA", "1", "250000.00", "Banco Aurora")],
      },
    ],
  },
  2: {
    internal: [
      h("PETR4", "ACOES", "9000", "342900.00"),
      h("VALE3", "ACOES", "2500", "158750.00"),
      h("BTC", "CRIPTO", "0.85", "297500.00"),
    ],
    external: [],
  },
  3: {
    internal: [
      h("WEGE3", "ACOES", "4100", "221810.00"),
      h("TESOURO-IPCA-2035", "RENDA_FIXA", "60", "268200.00"),
    ],
    external: [
      { institution: "Corretora Litoral", account_id: "LIT-4471", balance: "32100.00", holdings: [] },
    ],
  },
  4: {
    internal: [
      h("BBAS3", "ACOES", "5000", "139500.00"),
      h("HGLG11", "FUNDOS", "700", "112700.00"),
    ],
    external: [],
  },
  5: {
    internal: [
      h("CDB-XP-2026", "RENDA_FIXA", "1", "180000.00"),
      h("TESOURO-SELIC-2029", "RENDA_FIXA", "20", "290400.00"),
    ],
    external: [],
  },
  6: {
    internal: [
      h("TESOURO-SELIC-2029", "RENDA_FIXA", "15", "217800.00"),
      h("ITUB4", "ACOES", "1500", "52800.00"),
      h("HGLG11", "FUNDOS", "300", "48300.00"),
    ],
    external: [
      { institution: "Banco Aurora", account_id: "AUR-2210", balance: "18200.00", holdings: [] },
    ],
  },
};

const quotes: Record<string, Pick<Quote, "price" | "change_pct">> = {
  ITUB4: { price: "35.20", change_pct: "-3.10" },
  KNRI11: { price: "157.00", change_pct: "-0.40" },
  PETR4: { price: "38.10", change_pct: "2.35" },
  VALE3: { price: "63.50", change_pct: "-1.20" },
  BTC: { price: "350000.00", change_pct: "1.80" },
  WEGE3: { price: "54.10", change_pct: "-2.05" },
  BBAS3: { price: "27.90", change_pct: "0.45" },
  HGLG11: { price: "161.00", change_pct: "0.10" },
};

// Horário cheio a `days` dias de hoje, para a agenda sempre parecer atual.
function slotAt(days: number, hour: number, minutes = 0): TimeSlot {
  const start = new Date();
  start.setDate(start.getDate() + days);
  start.setHours(hour, minutes, 0, 0);
  return { start: start.toISOString(), end: new Date(start.getTime() + 30 * 60000).toISOString() };
}

const meetings: Meeting[] = [
  { id: 1, client_id: 1, advisor_id: ADVISOR_ID, slot: slotAt(1, 9, 30), topic: "Revisar exposição a ações" },
  { id: 2, client_id: 5, advisor_id: ADVISOR_ID, slot: slotAt(1, 14), topic: "CDB que vence este mês" },
  { id: 3, client_id: 3, advisor_id: ADVISOR_ID, slot: slotAt(3, 16), topic: "Proposta de rebalanceamento" },
];

const changeRequests: ChangeRequest[] = [
  {
    id: 1,
    client_id: 2,
    kind: "APORTE",
    message: "Quero aportar R$ 40 mil este mês. Onde faz mais sentido?",
    created_at: new Date(Date.now() - 3 * 3600000).toISOString(),
  },
];

const suitability = new Map<number, Suitability>();

const news: Omit<NewsImpact, "affected_clients">[] = [
  {
    id: 1,
    source: "InfoMoney",
    title: "ITUB4 recua 3,1% após revisão das projeções de crédito",
    summary: "Bancos puxam a queda do dia; analistas veem pressão no curto prazo.",
    url: "https://www.infomoney.com.br/mercados/ibovespa-e-ativos-brasileiros/",
    published_at: new Date(Date.now() - 50 * 60000).toISOString(),
    related_tickers: ["ITUB4"],
    sentiment: "NEGATIVE",
  },
  {
    id: 2,
    source: "InfoMoney",
    title: "WEGE3 cai 2,05% com realização de lucros",
    summary: "Papel devolve parte da alta do trimestre; sem mudança nos fundamentos.",
    url: "https://www.infomoney.com.br/mercados/bolsa-e-empresas/",
    published_at: new Date(Date.now() - 2 * 3600000).toISOString(),
    related_tickers: ["WEGE3"],
    sentiment: "NEGATIVE",
  },
  {
    id: 3,
    source: "InfoMoney",
    title: "Petróleo sobe e PETR4 avança 2,35%",
    summary: "Alta do barril favorece as petroleiras no pregão de hoje.",
    url: "https://www.infomoney.com.br/mercados/petroleo-bens-commodities/",
    published_at: new Date(Date.now() - 4 * 3600000).toISOString(),
    related_tickers: ["PETR4"],
    sentiment: "POSITIVE",
  },
  {
    id: 4,
    source: "InfoMoney",
    title: "Ata do Copom reforça Selic estável nas próximas reuniões",
    summary: "Títulos pós-fixados seguem com retorno previsível; atenção aos vencimentos.",
    url: "https://www.infomoney.com.br/onde-investir/titulos-do-tesouro-disparam-ate-13-em-uma-semana-e-batem-ibovespa/",
    published_at: new Date(Date.now() - 7 * 3600000).toISOString(),
    related_tickers: ["TESOURO-SELIC-2029", "CDB-XP-2026"],
    sentiment: "NEUTRAL",
  },
];

const sum = (values: string[]) => values.reduce((acc, v) => acc + Number(v), 0);

// Simula latência de rede para a UI exercitar os estados de carregamento.
const delay = <T,>(value: T, ms = 350) =>
  new Promise<T>((resolve) => setTimeout(() => resolve(value), ms));

function findClient(clientId: number): ClientProfile {
  const client = clients.find((c) => c.user.id === clientId);
  if (!client) throw new Error(`Cliente ${clientId} não encontrado`);
  return client;
}

const allHoldings = (clientId: number) => {
  const p = portfolios[clientId] ?? { internal: [], external: [] };
  return [...p.internal, ...p.external.flatMap((a) => a.holdings)];
};

const netWorth = (clientId: number) => {
  const p = portfolios[clientId] ?? { internal: [], external: [] };
  return sum(allHoldings(clientId).map((x) => x.market_value)) + sum(p.external.map((a) => a.balance));
};

const getSuit = (clientId: number): Suitability =>
  suitability.get(clientId) ?? { client_id: clientId, answers: [], risk_profile: null };

// 4 perguntas de 0 a 2 pontos; texto livre conta como resposta do meio.
function scoreProfile(s: Suitability): RiskProfile | null {
  const required = REQUIRED.map((q) => s.answers.find((a) => a.question_id === q.id));
  if (required.some((a) => !a)) return null;
  const points = required.reduce((acc, a) => acc + (a!.option_index ?? 1), 0);
  return points <= 2 ? "CONSERVADOR" : points <= 5 ? "MODERADO" : "ARROJADO";
}

const splitList = (text: string) =>
  text.split(/,|;| e /).map((s) => s.trim()).filter(Boolean);

const RISK_PROFILES: RiskProfile[] = ["CONSERVADOR", "MODERADO", "ARROJADO"];

const pct = (part: number, total: number) =>
  total ? Math.round((part / total) * 10000) / 100 : 0;

// Mesma consolidação de src/modules/advisor_dashboard/overview.py.
function buildOverview(advisorId: number): AdvisorOverview {
  const mine = clients.filter((c) => c.advisor_id === advisorId);
  const byClass = new Map<AssetClass, number>();
  const byTicker = new Map<string, { asset_class: AssetClass; value: number; clients: Set<number> }>();
  const segments = new Map(RISK_PROFILES.map((p) => [p, { count: 0, aum: 0 }]));
  let total = 0;
  let externalAum = 0;
  let externalCash = 0;

  for (const client of mine) {
    const p = portfolios[client.user.id] ?? { internal: [], external: [] };
    const externalHoldings = p.external.flatMap((a) => a.holdings);
    const cash = sum(p.external.map((a) => a.balance));
    let clientTotal = cash;

    for (const holding of [...p.internal, ...externalHoldings]) {
      const value = Number(holding.market_value);
      clientTotal += value;
      byClass.set(holding.asset_class, (byClass.get(holding.asset_class) ?? 0) + value);
      const entry = byTicker.get(holding.ticker) ?? {
        asset_class: holding.asset_class,
        value: 0,
        clients: new Set<number>(),
      };
      entry.value += value;
      entry.clients.add(client.user.id);
      byTicker.set(holding.ticker, entry);
    }

    externalCash += cash;
    externalAum += cash + sum(externalHoldings.map((x) => x.market_value));
    total += clientTotal;
    const segment = segments.get(client.risk_profile)!;
    segment.count += 1;
    segment.aum += clientTotal;
  }

  return {
    advisor_id: advisorId,
    clients_count: mine.length,
    total_aum: total.toFixed(2),
    external_aum: externalAum.toFixed(2),
    external_cash: externalCash.toFixed(2),
    by_asset_class: [...byClass]
      .sort((a, b) => b[1] - a[1])
      .map(([asset_class, value]) => ({
        asset_class,
        total_value: value.toFixed(2),
        share_pct: pct(value, total),
      })),
    holdings: [...byTicker]
      .sort((a, b) => b[1].value - a[1].value)
      .map(([ticker, e]) => ({
        ticker,
        asset_class: e.asset_class,
        total_value: e.value.toFixed(2),
        share_pct: pct(e.value, total),
        clients_count: e.clients.size,
      })),
    segments: RISK_PROFILES.map((risk_profile) => {
      const s = segments.get(risk_profile)!;
      return {
        risk_profile,
        clients_count: s.count,
        total_aum: s.aum.toFixed(2),
        aum_share_pct: pct(s.aum, total),
      };
    }),
  };
}

export const mockApi: Api = {
  listProfiles: () =>
    delay(
      [
        advisor,
        ...clients.map((c) => ({
          id: c.user.id,
          name: c.user.name,
          email: c.user.email,
          role: c.user.role,
          needs_onboarding: pendingOnboarding.has(c.user.id),
        })),
      ],
      200,
    ),

  signUp: (name, email) => {
    const id = Math.max(...clients.map((c) => c.user.id)) + 1;
    clients.push({
      user: { id, name, email, role: "CLIENT" },
      advisor_id: ADVISOR_ID,
      risk_profile: "MODERADO",
      context: { hobbies: [], favorite_team: null, family_dates: [] },
    });
    pendingOnboarding.add(id);
    priorities.push({
      client_id: id,
      criticality_score: 30,
      next_best_action: {
        title: "Dar as boas-vindas",
        rationale: "Conta criada hoje; ainda sem investimentos na plataforma.",
      },
    });
    return delay({ id, name, email, role: "CLIENT" as const, needs_onboarding: true });
  },

  getNews: (advisorId) => {
    const mine = clients.filter((c) => c.advisor_id === advisorId);
    return delay(
      news.map((n) => ({
        ...n,
        affected_clients: mine
          .map((c) => {
            const exposure = sum(
              allHoldings(c.user.id)
                .filter((x) => n.related_tickers.includes(x.ticker))
                .map((x) => x.market_value),
            );
            return {
              client_id: c.user.id,
              client_name: c.user.name,
              exposure_value: exposure.toFixed(2),
              exposure_pct: pct(exposure, netWorth(c.user.id)),
            };
          })
          .filter((a) => Number(a.exposure_value) > 0)
          .sort((a, b) => b.exposure_pct - a.exposure_pct),
      })),
    );
  },

  getMeetings: (advisorId) =>
    delay(
      meetings
        .filter((m) => m.advisor_id === advisorId)
        .sort((a, b) => a.slot.start.localeCompare(b.slot.start)),
    ),

  getFreeSlots: (advisorId) => {
    const taken = new Set(meetings.filter((m) => m.advisor_id === advisorId).map((m) => m.slot.start));
    const slots = [1, 2, 3].flatMap((d) => [slotAt(d, 10), slotAt(d, 11, 30), slotAt(d, 15)]);
    return delay(slots.filter((s) => !taken.has(s.start)).slice(0, 6), 200);
  },

  getChangeRequests: (advisorId) =>
    delay(
      changeRequests
        .filter((r) => findClient(r.client_id).advisor_id === advisorId)
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    ),

  getSuitability: (clientId) => {
    const s = getSuit(clientId);
    // Clientes antigos da demo já têm perfil definido, sem respostas guardadas.
    const known = pendingOnboarding.has(clientId) ? s.risk_profile : findClient(clientId).risk_profile;
    return delay({ ...s, risk_profile: known }, 200);
  },

  answerSuitability: (clientId, answer) => {
    const prev = getSuit(clientId);
    const next: Suitability = {
      ...prev,
      answers: [...prev.answers.filter((a) => a.question_id !== answer.question_id), answer],
    };
    const client = findClient(clientId);
    const profile = scoreProfile(next);
    if (profile) {
      next.risk_profile = profile;
      client.risk_profile = profile;
      pendingOnboarding.delete(clientId);
    }
    if (answer.question_id === "hobbies") client.context.hobbies = splitList(answer.answer);
    if (answer.question_id === "time") client.context.favorite_team = answer.answer;
    suitability.set(clientId, next);
    const known = profile ?? (pendingOnboarding.has(clientId) ? null : client.risk_profile);
    return delay({ ...next, risk_profile: known }, 450);
  },

  clearSuitabilityAnswer: (clientId, questionId) => {
    const prev = getSuit(clientId);
    const next: Suitability = {
      ...prev,
      answers: prev.answers.filter((a) => a.question_id !== questionId),
    };
    suitability.set(clientId, next);
    return delay({ ...next, risk_profile: next.risk_profile ?? null }, 200);
  },

  resetSuitability: (clientId) => {
    const client = findClient(clientId);
    suitability.delete(clientId);
    client.risk_profile = "MODERADO";
    pendingOnboarding.add(clientId);
    return delay({ client_id: clientId, answers: [], risk_profile: null }, 200);
  },

  transcribe: async (audio) => {
    const text = audio.size > 0 ? `Transcrição simulada de ${audio.type || "áudio"}` : "";
    return delay({ text }, 200);
  },

  requestChange: (req) => {
    const created: ChangeRequest = {
      ...req,
      id: changeRequests.length + 1,
      created_at: new Date().toISOString(),
    };
    changeRequests.push(created);
    return delay(created);
  },

  getOverview: (advisorId) => delay(buildOverview(advisorId)),

  getPriorities: (advisorId) =>
    delay(priorities.filter((p) => findClient(p.client_id).advisor_id === advisorId)),

  getClient: (clientId) => delay(findClient(clientId)),

  getPortfolio: (clientId) => {
    const p = portfolios[clientId] ?? { internal: [], external: [] };
    const total =
      sum(p.internal.map((x) => x.market_value)) +
      sum(p.external.map((a) => a.balance)) +
      sum(p.external.flatMap((a) => a.holdings.map((x) => x.market_value)));
    return delay({
      client_id: clientId,
      internal_holdings: p.internal,
      external_accounts: p.external,
      total_net_worth: total.toFixed(2),
    });
  },

  getQuote: (ticker) => {
    const q = quotes[ticker];
    return delay(q ? { ticker, ...q, timestamp: new Date().toISOString() } : null, 150);
  },

  getCurrencyLine: () =>
    delay(
      [
        { code: "BRL", name: "Real brasileiro", value: "5.31", variation_pct: "0.12", updated_at: new Date().toISOString() },
        { code: "EUR", name: "Euro", value: "0.92", variation_pct: "0.14", updated_at: new Date().toISOString() },
        { code: "GBP", name: "Libra esterlina", value: "0.78", variation_pct: "-0.08", updated_at: new Date().toISOString() },
        { code: "JPY", name: "Iene japonês", value: "149.20", variation_pct: "0.05", updated_at: new Date().toISOString() },
        { code: "CHF", name: "Franco suíço", value: "0.90", variation_pct: "0.04", updated_at: new Date().toISOString() },
        { code: "CAD", name: "Dólar canadense", value: "1.36", variation_pct: "0.03", updated_at: new Date().toISOString() },
        { code: "ARS", name: "Peso argentino", value: "1025.40", variation_pct: "0.02", updated_at: new Date().toISOString() },
      ],
      150,
    ),

  sendChat: ({ client_id, message }) => {
    const name = findClient(client_id).user.name.split(" ")[0];
    if (/reuni|agend/i.test(message)) {
      const slot = slotAt(2, 10);
      meetings.push({
        id: meetings.length + 1,
        client_id,
        advisor_id: ADVISOR_ID,
        slot,
        topic: "Pedido pelo chat",
      });
      return delay(
        {
          reply: `Claro, ${name}. Encontrei um horário livre com seu assessor e deixei a reunião pré-agendada.`,
          tool_calls: [{ name: "schedule_meeting", arguments: { client_id, advisor_id: ADVISOR_ID } }],
        },
        700,
      );
    }
    return delay(
      {
        reply: `${name}, esta é uma resposta simulada. Com o backend ligado, o Gemini responde aqui com base na sua carteira.`,
        tool_calls: [],
      },
      700,
    );
  },

  getChatHistory: (clientId) => {
    const items = [{ role: "USER" as const, content: `Olá, gostaria de revisar minha carteira (${clientId}).` }];
    return delay(items, 150);
  },

  getClientMeetings: (clientId) =>
    delay(
      meetings
        .filter((m) => m.client_id === clientId)
        .sort((a, b) => a.slot.start.localeCompare(b.slot.start)),
    ),

  confirmMeeting: async (meetingId, viewer) => {
    const found = meetings.find((m) => m.id === meetingId);
    if (!found) throw new Error(`Reunião ${meetingId} não encontrada`);
    found.status = "CONFIRMED";
    found.initiated_by = viewer.role === "CLIENT" ? "CLIENT" : "ADVISOR";
    return delay(found);
  },

  getMeetingBriefing: async (advisorId, meetingId) => {
    const meeting = meetings.find((m) => m.id === meetingId && m.advisor_id === advisorId);
    if (!meeting) throw new Error(`Briefing da reunião ${meetingId} não encontrado`);
    return delay({
      meeting,
      context: meeting.context ?? null,
      portfolio: {
        total_net_worth: "0.00",
        allocation: [],
      },
      news: [],
      talking_points: [],
    });
  },

  getNotes: (clientId) =>
    delay(
      [
        {
          id: 1,
          client_id: clientId,
          advisor_id: ADVISOR_ID,
          text: "Cliente gosta de conversar sobre risco e patrimônio em cenários de baixa.",
          created_at: new Date().toISOString(),
        },
      ],
      150,
    ),

  addNote: (clientId, advisorId, text) =>
    delay({
      id: Date.now(),
      client_id: clientId,
      advisor_id: advisorId,
      text,
      created_at: new Date().toISOString(),
    }),

  editNote: (noteId, text) =>
    delay({
      id: noteId,
      client_id: 0,
      advisor_id: ADVISOR_ID,
      text,
      created_at: new Date().toISOString(),
    }),

  deleteNote: async () => undefined,

  scheduleMeeting: (req) => {
    const start = new Date(Date.now() + 24 * 60 * 60 * 1000);
    const fallback = {
      start: start.toISOString(),
      end: new Date(start.getTime() + 30 * 60 * 1000).toISOString(),
    };
    const meeting: Meeting = {
      id: meetings.length + 1,
      client_id: req.client_id,
      advisor_id: req.advisor_id,
      slot: req.preferred ?? fallback,
      topic: req.topic ?? "",
      status: "PENDING",
      initiated_by: req.initiated_by ?? "CLIENT",
      context: req.context ?? null,
    };
    meetings.push(meeting);
    return delay(meeting);
  },
};
