// Espelha os modelos Pydantic de src/modules/*/models.py.
// Decimal chega como string no JSON do Pydantic v2; datas chegam em ISO 8601.

export type Decimal = string;

// accounts
export type UserRole = "ADVISOR" | "CLIENT";
export type RiskProfile = "CONSERVADOR" | "MODERADO" | "ARROJADO";

export interface FamilyDate {
  label: string;
  date: string;
}

export interface PersonalContext {
  hobbies: string[];
  favorite_team: string | null;
  family_dates: FamilyDate[];
}

export interface User {
  id: number;
  name: string;
  email: string;
  role: UserRole;
}

export interface ClientProfile {
  user: User;
  advisor_id: number;
  risk_profile: RiskProfile;
  context: PersonalContext;
}

// portfolio
export type AssetClass = "RENDA_FIXA" | "ACOES" | "FUNDOS" | "CRIPTO" | "OUTROS";

export interface Holding {
  ticker: string;
  asset_class: AssetClass;
  quantity: Decimal;
  market_value: Decimal;
  institution: string;
}

export interface ExternalAccount {
  institution: string;
  account_id: string;
  balance: Decimal;
  holdings: Holding[];
}

export interface UnifiedPortfolio {
  client_id: number;
  internal_holdings: Holding[];
  external_accounts: ExternalAccount[];
  total_net_worth: Decimal;
}

// market_intelligence
export interface Quote {
  ticker: string;
  price: Decimal;
  change_pct: Decimal;
  timestamp: string;
}

export interface CurrencyRate {
  code: string;
  name: string;
  value: Decimal;
  variation_pct: Decimal;
  updated_at: string;
}

// advisor_dashboard
export interface NextBestAction {
  title: string;
  rationale: string;
}

export interface PrioritizedClient {
  client_id: number;
  criticality_score: number;
  next_best_action: NextBestAction;
}

export interface AssetClassAllocation {
  asset_class: AssetClass;
  total_value: Decimal;
  share_pct: number;
}

export interface ConsolidatedHolding {
  ticker: string;
  asset_class: AssetClass;
  total_value: Decimal;
  share_pct: number;
  clients_count: number;
}

export interface ClientSegment {
  risk_profile: RiskProfile;
  clients_count: number;
  total_aum: Decimal;
  aum_share_pct: number;
}

export interface AdvisorOverview {
  advisor_id: number;
  clients_count: number;
  total_aum: Decimal;
  external_aum: Decimal;
  external_cash: Decimal;
  by_asset_class: AssetClassAllocation[];
  holdings: ConsolidatedHolding[];
  segments: ClientSegment[];
}

// copilot_chat
export interface ChatRequest {
  client_id: number;
  message: string;
}

export interface ToolCall {
  name: string;
  arguments: Record<string, unknown>;
}

export interface ChatResponse {
  reply: string;
  tool_calls: ToolCall[];
}

export interface ChatHistoryItem {
  role: "USER" | "ASSISTANT";
  content: string;
  tool_calls?: ToolCall[];
}

// scheduling
export type MeetingParty = "CLIENT" | "ADVISOR";
export type MeetingStatus = "PENDING" | "CONFIRMED" | "CANCELLED" | "DONE";

export interface TimeSlot {
  start: string;
  end: string;
}

export interface ContextAnswer {
  key: string;
  question: string;
  answer: string;
}

export interface MeetingContext {
  answers: ContextAnswer[];
  summary?: string;
}

export interface MeetingRequest {
  client_id: number;
  advisor_id: number;
  preferred?: TimeSlot | null;
  topic?: string;
  initiated_by?: MeetingParty;
  context?: MeetingContext | null;
}

export interface Meeting {
  id: number;
  client_id: number;
  advisor_id: number;
  slot: TimeSlot;
  topic: string;
  status?: MeetingStatus;
  initiated_by?: MeetingParty;
  context?: MeetingContext | null;
}

export interface MeetingConfirm {
  user_id: number;
  role: MeetingParty;
}

// Perfis prontos da tela de entrada (demo sem senha).
export interface LoginProfile {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  needs_onboarding: boolean;
}

// market_intelligence: notícia cruzada com as carteiras do assessor
export type Sentiment = "POSITIVE" | "NEUTRAL" | "NEGATIVE";

export interface AffectedClient {
  client_id: number;
  client_name: string;
  exposure_value: Decimal;
  exposure_pct: number;
}

export interface NewsImpact {
  id: number;
  source: string;
  title: string;
  summary: string;
  url?: string;
  published_at: string;
  related_tickers: string[];
  sentiment: Sentiment;
  affected_clients: AffectedClient[];
}

// portfolio: pedido do cliente que vira alerta para o assessor
export type ChangeKind = "APORTE" | "RESGATE" | "REBALANCEAMENTO";

export interface ChangeRequestCreate {
  client_id: number;
  kind: ChangeKind;
  message: string;
}

export interface ChangeRequest extends ChangeRequestCreate {
  id: number;
  created_at: string;
}

// accounts: análise de perfil (suitability)
export interface SuitabilityAnswer {
  question_id: string;
  answer: string;
  // Índice da opção escolhida; null quando o cliente respondeu em texto livre.
  option_index: number | null;
}

export interface Suitability {
  client_id: number;
  answers: SuitabilityAnswer[];
  risk_profile: RiskProfile | null;
}

/** Contrato único consumido pela UI; implementado por http.ts e mock.ts. */
export interface AdvisorNote {
  id: number;
  client_id: number;
  advisor_id: number;
  text: string;
  created_at: string;
}

export interface BriefingNews {
  source: string;
  title: string;
  published_at: string;
  sentiment: Sentiment;
}

export interface MeetingBriefing {
  meeting: Meeting;
  context: MeetingContext | null;
  portfolio: {
    total_net_worth: Decimal;
    allocation: Array<{ asset_class: AssetClass; value: Decimal; share_pct: number }>;
  };
  news: BriefingNews[];
  talking_points: string[];
}

export interface Api {
  listProfiles(): Promise<LoginProfile[]>;
  signUp(name: string, email: string): Promise<LoginProfile>;
  getOverview(advisorId: number): Promise<AdvisorOverview>;
  getPriorities(advisorId: number): Promise<PrioritizedClient[]>;
  getNews(advisorId: number): Promise<NewsImpact[]>;
  getMeetings(advisorId: number): Promise<Meeting[]>;
  getClientMeetings(clientId: number): Promise<Meeting[]>;
  getFreeSlots(advisorId: number): Promise<TimeSlot[]>;
  getChangeRequests(advisorId: number): Promise<ChangeRequest[]>;
  getClient(clientId: number): Promise<ClientProfile>;
  getPortfolio(clientId: number): Promise<UnifiedPortfolio>;
  getQuote(ticker: string): Promise<Quote | null>;
  getCurrencyLine(): Promise<CurrencyRate[]>;
  getSuitability(clientId: number): Promise<Suitability>;
  answerSuitability(clientId: number, answer: SuitabilityAnswer): Promise<Suitability>;
  clearSuitabilityAnswer(clientId: number, questionId: string): Promise<Suitability>;
  resetSuitability(clientId: number): Promise<Suitability>;
  transcribe(audio: Blob): Promise<{ text: string }>;
  requestChange(req: ChangeRequestCreate): Promise<ChangeRequest>;
  sendChat(req: ChatRequest): Promise<ChatResponse>;
  getChatHistory(clientId: number): Promise<ChatHistoryItem[]>;
  scheduleMeeting(req: MeetingRequest): Promise<Meeting>;
  confirmMeeting(meetingId: number, viewer: { id: number; role: UserRole }): Promise<Meeting>;
  getMeetingBriefing(advisorId: number, meetingId: number): Promise<MeetingBriefing>;
  getNotes(clientId: number): Promise<AdvisorNote[]>;
  addNote(clientId: number, advisorId: number, text: string): Promise<AdvisorNote>;
  editNote(noteId: number, text: string): Promise<AdvisorNote>;
  deleteNote(noteId: number): Promise<void>;
}
