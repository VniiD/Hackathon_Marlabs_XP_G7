import type { ReactNode } from "react";

import type { Holding, RiskProfile, UnifiedPortfolio } from "../api";
import {
  ASSET_COLOR,
  ASSET_LABEL,
  CASH_COLOR,
  RISK_LABEL,
  formatBRL,
  formatShare,
  initials,
  severity,
  type Async,
} from "../lib";

const ICONS = {
  back: "M15 5l-7 7 7 7",
  send: "M4 12h15M13 6l6 6-6 6",
  mic: "M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM5 11a7 7 0 0 0 14 0M12 18v3",
  plus: "M12 5v14M5 12h14",
  check: "M5 12.5l4.5 4.5L19 7.5",
  chevron: "M9 5l7 7-7 7",
  stop: "M7 7h10v10H7z",
  note: "M6 4h12v10l-5 6H6zM13 20v-6h5",
  edit: "M4 20h4L19 9l-4-4L4 16zM13 7l4 4",
  close: "M6 6l12 12M18 6L6 18",
  trash: "M5 7h14M10 7V5h4v2M7 7l1 12h8l1-12M10 11v5M14 11v5",
};

export function Icon({ name, size = 18 }: { name: keyof typeof ICONS; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={ICONS[name]} />
    </svg>
  );
}

export function Avatar({ name, size = "md" }: { name: string; size?: "sm" | "md" | "xl" }) {
  return (
    <span className={`avatar avatar-${size}`} aria-hidden="true">
      {initials(name)}
    </span>
  );
}

export function RiskTag({ profile }: { profile: RiskProfile }) {
  return <span className="tag">{RISK_LABEL[profile]}</span>;
}

// Forma + rótulo: a criticidade nunca depende só da cor.
export function Severity({ score, showScore = false }: { score: number; showScore?: boolean }) {
  const s = severity(score);
  return (
    <span className={`sev sev-${s.level}`}>
      <span className="sev-mark" aria-hidden="true" />
      {s.label}
      {showScore && <span className="sev-score">{Math.round(score)}</span>}
    </span>
  );
}

/** Estados de carregamento e erro no mesmo padrão em todas as telas. */
export function Load<T>({
  state,
  label,
  children,
}: {
  state: Async<T>;
  label: string;
  children: (data: T) => ReactNode;
}) {
  if (state.status === "loading") {
    return (
      <p className="state" role="status">
        Carregando {label}…
      </p>
    );
  }
  if (state.status === "error") {
    return (
      <p className="state state-error" role="alert">
        Não foi possível carregar {label}. Tente novamente. <span className="muted">({state.error})</span>
      </p>
    );
  }
  return <>{children(state.data)}</>;
}

export interface Part {
  key: string;
  label: string;
  value: number;
  color: string;
}

interface StripProps {
  parts: Part[];
  selected?: string | null;
  onSelect?: (key: string | null) => void;
  size?: "md" | "lg";
}

/** Faixa de composição: uma barra 100% e a legenda com os valores exatos. */
export function AllocationStrip({ parts, selected = null, onSelect, size = "md" }: StripProps) {
  const total = parts.reduce((acc, p) => acc + p.value, 0);
  if (total === 0) return null;
  const share = (p: Part) => (p.value / total) * 100;
  const toggle = (key: string) => onSelect?.(selected === key ? null : key);

  return (
    <div className={`strip strip-${size}`}>
      <div className="strip-bar" aria-hidden="true">
        {parts.map((p) => (
          <span
            key={p.key}
            className={selected && selected !== p.key ? "strip-seg is-dim" : "strip-seg"}
            style={{ flexGrow: p.value, background: p.color }}
            title={`${p.label}: ${formatBRL(p.value)} (${formatShare(share(p))})`}
            onClick={onSelect ? () => toggle(p.key) : undefined}
          />
        ))}
      </div>
      <ul className="strip-legend">
        {parts.map((p) => {
          const body = (
            <>
              <span className="swatch" style={{ background: p.color }} />
              <span className="strip-label">{p.label}</span>
              <span className="strip-share">{formatShare(share(p))}</span>
              <span className="strip-value">{formatBRL(p.value)}</span>
            </>
          );
          return (
            <li key={p.key}>
              {onSelect ? (
                <button
                  type="button"
                  className={selected === p.key ? "strip-row is-selected" : "strip-row"}
                  aria-pressed={selected === p.key}
                  onClick={() => toggle(p.key)}
                >
                  {body}
                </button>
              ) : (
                <span className="strip-row">{body}</span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Agrupa a carteira unificada por classe, com o saldo em conta à parte. */
export function portfolioParts(p: UnifiedPortfolio): Part[] {
  const byClass = new Map<Holding["asset_class"], number>();
  const all = [...p.internal_holdings, ...p.external_accounts.flatMap((a) => a.holdings)];
  for (const h of all) {
    byClass.set(h.asset_class, (byClass.get(h.asset_class) ?? 0) + Number(h.market_value));
  }
  const parts: Part[] = [...byClass]
    .sort((a, b) => b[1] - a[1])
    .map(([c, value]) => ({ key: c, label: ASSET_LABEL[c], value, color: ASSET_COLOR[c] }));
  const cash = p.external_accounts.reduce((acc, a) => acc + Number(a.balance), 0);
  if (cash > 0) parts.push({ key: "CASH", label: "Saldo em conta", value: cash, color: CASH_COLOR });
  return parts;
}
