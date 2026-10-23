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
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const httpApi: Api = {
  listProfiles: () => request("/accounts/profiles"),
  signUp: (name, email) => post("/accounts/signup", { name, email }),
  getNews: (advisorId) => request(`/advisor/${advisorId}/news-impact`),
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
  transcribe: async (audio) => {
    const res = await fetch(`${BASE_URL}/copilot/transcribe`, {
      method: "POST",
      headers: { "Content-Type": audio.type || "application/octet-stream" },
      body: audio,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new ApiError(res.status, body?.detail ?? res.statusText);
    }
    return res.json() as Promise<{ text: string }>;
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
  getNotes: (clientId, advisorId) =>
    request(`/accounts/advisors/${advisorId}/clients/${clientId}/notes`),
  addNote: (clientId, advisorId, text) =>
    post(`/accounts/advisors/${advisorId}/clients/${clientId}/notes`, { text }),
  editNote: (noteId, advisorId, text) =>
    request(`/accounts/advisors/${advisorId}/notes/${noteId}`, {
      method: "PATCH",
      body: JSON.stringify({ text }),
    }),
  deleteNote: (noteId, advisorId) =>
    request(`/accounts/advisors/${advisorId}/notes/${noteId}`, { method: "DELETE" }),
};
