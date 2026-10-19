from src.modules.advisor_dashboard.models import (
    ClientSignals,
    NextBestAction,
    PrioritizedClient,
    TriggerType,
)

# Quanto maior a aversão a risco, mais uma queda pesa no score.
_RISK_WEIGHT = {"CONSERVADOR": 3.0, "MODERADO": 2.0, "ARROJADO": 1.0}


class DailyAdvisorEngine:
    """Calcula criticidade diária cruzando mercado, perfil e gatilhos de relacionamento."""

    def score(self, s: ClientSignals) -> float:
        drop = max(0.0, -s.portfolio_change_pct)
        market = drop * _RISK_WEIGHT.get(s.risk_profile, 2.0) * 5
        relationship = 10 * len(s.relationship_triggers)
        inactivity = min(s.days_since_last_contact / 3, 30)
        return min(100.0, market + relationship + inactivity)

    def next_best_action(self, s: ClientSignals) -> NextBestAction:
        if s.portfolio_change_pct < 0 and s.risk_profile == "CONSERVADOR":
            return NextBestAction(
                title="Ligar para acalmar e revisar exposição",
                rationale="Queda na carteira de perfil conservador.",
            )
        if TriggerType.BIRTHDAY in s.relationship_triggers:
            return NextBestAction(title="Enviar felicitações", rationale="Aniversário do cliente.")
        return NextBestAction(
            title="Contato de acompanhamento", rationale="Rotina de relacionamento."
        )

    def prioritize(self, signals: list[ClientSignals]) -> list[PrioritizedClient]:
        ranked = [
            PrioritizedClient(
                client_id=s.client_id,
                criticality_score=self.score(s),
                next_best_action=self.next_best_action(s),
            )
            for s in signals
        ]
        return sorted(ranked, key=lambda c: c.criticality_score, reverse=True)
