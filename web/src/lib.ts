import { useEffect, useState } from "react";

import type { AssetClass, RiskProfile } from "./api";

// Nome do produto; troque aqui para mudar em todas as telas.
export const APP_NAME = "XP.inc";

export const RISK_LABEL: Record<RiskProfile, string> = {
  CONSERVADOR: "Conservador",
  MODERADO: "Moderado",
  ARROJADO: "Arrojado",
};

export const RISK_HINT: Record<RiskProfile, string> = {
  CONSERVADOR: "Prioriza segurança e previsibilidade, com pouca oscilação.",
  MODERADO: "Aceita alguma oscilação em troca de retorno maior no médio prazo.",
  ARROJADO: "Tolera oscilações fortes buscando crescimento no longo prazo.",
};

export const ASSET_LABEL: Record<AssetClass, string> = {
  RENDA_FIXA: "Renda fixa",
  ACOES: "Ações",
  FUNDOS: "Fundos",
  CRIPTO: "Cripto",
  OUTROS: "Outros",
};

// Cor fixa por classe: a mesma em todas as telas, validada para o fundo escuro.
export const ASSET_COLOR: Record<AssetClass, string> = {
  RENDA_FIXA: "var(--series-1)",
  ACOES: "var(--series-2)",
  FUNDOS: "var(--series-3)",
  CRIPTO: "var(--series-4)",
  OUTROS: "var(--series-5)",
};

export const CASH_COLOR = "var(--series-cash)";

export const formatShare = (pct: number) => `${pct.toFixed(1).replace(".", ",")}%`;

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const brlShort = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

export const formatBRL = (value: string | number) => brl.format(Number(value));
export const formatBRLShort = (value: string | number) => brlShort.format(Number(value));

export const formatPct = (value: string | number) => {
  const n = Number(value);
  return `${n > 0 ? "+" : ""}${n.toFixed(2).replace(".", ",")}%`;
};

export const formatDate = (iso: string) =>
  new Date(iso.length === 10 ? `${iso}T00:00:00` : iso).toLocaleDateString("pt-BR");

export const formatTime = (iso: string) =>
  new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();

/** "Hoje", "Amanhã" ou "seg., 12 de out." */
export function formatDay(iso: string) {
  const date = new Date(iso);
  const days = Math.round((startOfDay(date) - startOfDay(new Date())) / 86400000);
  if (days === 0) return "Hoje";
  if (days === 1) return "Amanhã";
  return date.toLocaleDateString("pt-BR", { weekday: "short", day: "numeric", month: "short" });
}

export const formatSlot = (iso: string) => `${formatDay(iso)}, ${formatTime(iso)}`;

export function formatAgo(iso: string) {
  const minutes = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 60) return `há ${minutes} min`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `há ${hours} h` : formatDate(iso);
}

export const initials = (name: string) => {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
};

export const firstName = (name: string) => name.trim().split(/\s+/)[0];

export function severity(score: number): { level: "high" | "medium" | "low"; label: string } {
  if (score >= 70) return { level: "high", label: "Crítico" };
  if (score >= 40) return { level: "medium", label: "Atenção" };
  return { level: "low", label: "Estável" };
}

export const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e));

export type Async<T> =
  | { status: "loading" }
  | { status: "error"; error: string }
  | { status: "ready"; data: T };

/** Roda `load` quando `deps` mudam e descarta respostas de chamadas antigas. */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): Async<T> {
  const [state, setState] = useState<Async<T>>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    load()
      .then((data) => !cancelled && setState({ status: "ready", data }))
      .catch((e: unknown) => !cancelled && setState({ status: "error", error: errorText(e) }));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}
