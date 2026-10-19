import { api, type Holding, type Quote, type UnifiedPortfolio } from "../api";
import { APP_NAME, ASSET_LABEL, formatBRL, formatPct } from "../lib";
import { AllocationStrip, portfolioParts } from "./ui";

export async function loadPortfolio(clientId: number) {
  const portfolio = await api.getPortfolio(clientId);
  const tickers = [...new Set(portfolio.internal_holdings.map((h) => h.ticker))];
  const found = await Promise.all(tickers.map((t) => api.getQuote(t)));
  const quotes = new Map<string, Quote>();
  found.forEach((q) => q && quotes.set(q.ticker, q));
  return { portfolio, quotes };
}

function Change({ value }: { value?: string }) {
  if (!value) return <td className="num muted">sem cotação</td>;
  const n = Number(value);
  return <td className={`num ${n < 0 ? "down" : n > 0 ? "up" : ""}`}>{formatPct(value)}</td>;
}

function HoldingsTable({ holdings, quotes }: { holdings: Holding[]; quotes?: Map<string, Quote> }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Ativo</th>
            <th className="col-opt">Classe</th>
            {quotes && <th className="num">Hoje</th>}
            <th className="num">Valor</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => (
            <tr key={`${h.institution}-${h.ticker}`}>
              <td>{h.ticker}</td>
              <td className="muted col-opt">{ASSET_LABEL[h.asset_class]}</td>
              {quotes && <Change value={quotes.get(h.ticker)?.change_pct} />}
              <td className="num">{formatBRL(h.market_value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface Props {
  portfolio: UnifiedPortfolio;
  quotes: Map<string, Quote>;
  title: string;
}

/** Patrimônio unificado: total, composição e posições por instituição. */
export function PortfolioView({ portfolio, quotes, title }: Props) {
  const external = portfolio.external_accounts;
  const empty = portfolio.internal_holdings.length === 0 && external.length === 0;

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>{title}</h2>
        <p className="figure">{formatBRL(portfolio.total_net_worth)}</p>
        <p className="muted">
          {external.length === 0
            ? "Nenhuma outra instituição conectada pelo Open Finance."
            : `Inclui ${external.length === 1 ? "1 instituição conectada" : `${external.length} instituições conectadas`} pelo Open Finance.`}
        </p>
      </header>

      {empty ? (
        <p className="empty">Ainda não há investimentos nesta carteira.</p>
      ) : (
        <>
          <AllocationStrip parts={portfolioParts(portfolio)} size="lg" />

          {portfolio.internal_holdings.length > 0 && (
            <>
              <h3>Na {APP_NAME}</h3>
              <HoldingsTable holdings={portfolio.internal_holdings} quotes={quotes} />
            </>
          )}

          {external.map((account) => (
            <div key={account.account_id}>
              <h3>
                {account.institution} <span className="tag">Open Finance</span>
              </h3>
              <p className="muted">Saldo em conta: {formatBRL(account.balance)}</p>
              {account.holdings.length > 0 && <HoldingsTable holdings={account.holdings} />}
            </div>
          ))}
        </>
      )}
    </section>
  );
}
