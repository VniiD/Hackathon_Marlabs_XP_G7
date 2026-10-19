import type { Api } from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

// Rotas marcadas com "pendente" ainda não existem no FastAPI.
export const httpApi: Api = {
  listProfiles: () => request("/accounts/profiles"),
  signUp: (name, email) => post("/accounts/signup", { name, email }),
  getNews: async (_advisorId) => {
    const items = await request<Array<{
      source: string;
      title: string;
      url: string;
      published_at: string;
      related_tickers: string[];
      sentiment: "POSITIVE" | "NEUTRAL" | "NEGATIVE";
    }>>(`/market/news`);
    return items.map((n, index) => ({
      id: index + 1,
      source: n.source,
      title: n.title,
      summary: n.title,
      url: n.url,
      published_at: n.published_at,
      related_tickers: n.related_tickers,
      sentiment: n.sentiment,
      affected_clients: [],
    }));
  },
  getMeetings: (advisorId) => request(`/scheduling/advisors/${advisorId}/meetings`),
  getClientMeetings: (clientId) => request(`/scheduling/clients/${clientId}/meetings`),
  getFreeSlots: (advisorId) => request(`/scheduling/advisors/${advisorId}/free-slots`),
  getChangeRequests: (advisorId) => request(`/advisor/${advisorId}/change-requests`),
  getSuitability: (clientId) => request(`/accounts/clients/${clientId}/suitability`),
  answerSuitability: (clientId, answer) =>
    post(`/accounts/clients/${clientId}/suitability`, answer),
  clearSuitabilityAnswer: async (_clientId, _questionId) => {
    throw new ApiError(501, "Limpar resposta da análise de perfil ainda não está disponível na API real.");
  },
  resetSuitability: async (_clientId) => {
    throw new ApiError(501, "Reiniciar a análise de perfil ainda não está disponível na API real.");
  },
  transcribe: async (_audio) => {
    throw new ApiError(501, "Transcrição de áudio ainda não está disponível na API real.");
  },
  requestChange: (req) => post(`/portfolio/${req.client_id}/change-requests`, req),
  getOverview: (advisorId) => request(`/advisor/${advisorId}/overview`),
  getPriorities: (advisorId) => request(`/advisor/${advisorId}/priorities`),
  getClient: (clientId) => request(`/accounts/clients/${clientId}`),
  getPortfolio: (clientId) => request(`/portfolio/${clientId}`),
  getQuote: async (ticker) => {
    try {
      return await request(`/market/quotes/${encodeURIComponent(ticker)}`);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null;
      throw e;
    }
  },
  getCurrencyLine: () => request("/market/currency-line"),
  sendChat: (req) => post("/copilot/chat", req),
  getChatHistory: (clientId) => request(`/copilot/chat/${clientId}/history`),
  scheduleMeeting: (req) => post("/scheduling/meetings", req),
  confirmMeeting: async (meetingId, viewer) =>
    post(`/scheduling/meetings/${meetingId}/confirm`, {
      user_id: viewer.id,
      role: viewer.role === "ADVISOR" ? "ADVISOR" : "CLIENT",
    }),
  getMeetingBriefing: async (advisorId, meetingId) =>
    request(`/advisor/${advisorId}/meetings/${meetingId}/briefing`),
  getNotes: async (_clientId) => {
    throw new ApiError(501, "As anotações do assessor ainda não estão expostas pela API real.");
  },
  addNote: async (_clientId, _advisorId, _text) => {
    throw new ApiError(501, "Adicionar anotações ainda não está disponível na API real.");
  },
  editNote: async (_noteId, _text) => {
    throw new ApiError(501, "Editar anotações ainda não está disponível na API real.");
  },
  deleteNote: async (_noteId) => {
    throw new ApiError(501, "Apagar anotações ainda não está disponível na API real.");
  },
};
