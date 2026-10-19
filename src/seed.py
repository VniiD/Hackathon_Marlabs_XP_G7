"""Carteiras e reuniões de demonstração para os stores em memória.

Os clientes vêm do banco (db/02_seed.sql); aqui só casamos pelo nome."""
from datetime import date
from decimal import Decimal

from src.core.database import SessionLocal
from src.modules.accounts.models import ClientCreate, FamilyDate, PersonalContext, RiskProfile
from src.modules.accounts.services import AccountsService
from src.modules.copilot_chat.tools import INTAKE_QUESTIONS, build_meeting_context
from src.modules.portfolio.models import AssetClass, ExternalAccount, Holding
from src.modules.portfolio.open_finance import get_open_finance_service
from src.modules.portfolio.services import get_portfolio_service
from src.modules.scheduling.models import ContextAnswer, MeetingParty, MeetingRequest
from src.modules.scheduling.services import get_scheduling_service

ADVISOR_ID = 1


def _h(ticker: str, asset_class: AssetClass, quantity: str, value: str, institution: str = "INTERNAL") -> Holding:
    return Holding(
        ticker=ticker,
        asset_class=asset_class,
        quantity=Decimal(quantity),
        market_value=Decimal(value),
        institution=institution,
    )


_RF, _AC, _FU, _CR = AssetClass.RENDA_FIXA, AssetClass.ACOES, AssetClass.FUNDOS, AssetClass.CRIPTO

_CLIENTS: list[tuple[ClientCreate, list[Holding], list[ExternalAccount]]] = [
    (
        ClientCreate(
            name="Helena Duarte",
            email="helena@exemplo.com",
            advisor_id=ADVISOR_ID,
            risk_profile=RiskProfile.CONSERVADOR,
            context=PersonalContext(
                hobbies=["Jardinagem", "Viagens"],
                favorite_team="Palmeiras",
                family_dates=[FamilyDate(label="Aniversário do neto", date=date(2026, 10, 18))],
            ),
        ),
        [
            _h("TESOURO-SELIC-2029", _RF, "42", "610000.00"),
            _h("ITUB4", _AC, "3200", "112640.00"),
            _h("KNRI11", _FU, "900", "141300.00"),
        ],
        [
            ExternalAccount(
                institution="Banco Aurora",
                account_id="AUR-0098",
                balance=Decimal("84500.00"),
                holdings=[_h("CDB-AURORA-2027", _RF, "1", "250000.00", "Banco Aurora")],
            )
        ],
    ),
    (
        ClientCreate(
            name="Rafael Monteiro",
            email="rafael@exemplo.com",
            advisor_id=ADVISOR_ID,
            risk_profile=RiskProfile.ARROJADO,
            context=PersonalContext(hobbies=["Ciclismo", "Vinhos"], favorite_team="Flamengo"),
        ),
        [
            _h("PETR4", _AC, "9000", "342900.00"),
            _h("VALE3", _AC, "2500", "158750.00"),
            _h("BTC", _CR, "0.85", "297500.00"),
        ],
        [],
    ),
    (
        ClientCreate(
            name="Beatriz Nogueira",
            email="beatriz@exemplo.com",
            advisor_id=ADVISOR_ID,
            risk_profile=RiskProfile.MODERADO,
            context=PersonalContext(
                hobbies=["Corrida"],
                family_dates=[
                    FamilyDate(label="Aniversário de casamento", date=date(2026, 11, 2))
                ],
            ),
        ),
        [
            _h("WEGE3", _AC, "4100", "221810.00"),
            _h("TESOURO-IPCA-2035", _RF, "60", "268200.00"),
        ],
        [
            ExternalAccount(
                institution="Corretora Litoral", account_id="LIT-4471", balance=Decimal("32100.00")
            )
        ],
    ),
    (
        ClientCreate(
            name="Otávio Lins",
            email="otavio@exemplo.com",
            advisor_id=ADVISOR_ID,
            risk_profile=RiskProfile.MODERADO,
            context=PersonalContext(hobbies=["Pesca", "Golfe"], favorite_team="Grêmio"),
        ),
        [_h("BBAS3", _AC, "5000", "139500.00"), _h("HGLG11", _FU, "700", "112700.00")],
        [],
    ),
    (
        ClientCreate(
            name="Camila Prates",
            email="camila@exemplo.com",
            advisor_id=ADVISOR_ID,
            risk_profile=RiskProfile.CONSERVADOR,
            context=PersonalContext(hobbies=["Leitura"], favorite_team="Corinthians"),
        ),
        [
            _h("CDB-XP-2026", _RF, "1", "180000.00"),
            _h("TESOURO-SELIC-2029", _RF, "20", "290400.00"),
        ],
        [],
    ),
]


_seeded = False


def seed_demo_data() -> None:
    global _seeded
    if _seeded:
        return
    _seeded = True
    with SessionLocal() as db:
        existing = AccountsService(db).list_clients_by_advisor(ADVISOR_ID)
    client_ids = {c.user.name: c.user.id for c in existing}
    open_finance = get_open_finance_service()
    portfolio = get_portfolio_service()
    for data, holdings, external in _CLIENTS:
        client_id = client_ids.get(data.name)
        if client_id is None:
            continue
        portfolio.set_internal_holdings(client_id, holdings)
        open_finance.link_external_accounts(client_id, external)
    _seed_meetings(client_ids)


# (cliente, pauta, quem pediu, já confirmada): um pedido de cada lado e uma reunião confirmada.
_MEETINGS = [
    ("Helena Duarte", "Revisar exposição a ações", MeetingParty.ADVISOR, False),
    ("Camila Prates", "CDB que vence este mês", MeetingParty.CLIENT, False),
    ("Beatriz Nogueira", "Proposta de rebalanceamento", MeetingParty.ADVISOR, True),
]


# Pedido do cliente pelo chat: já chega ao assessor com o contexto que o copiloto coletou.
_CAMILA_ANSWERS = {
    "motivo": "Meu CDB de R$ 180 mil vence este mês e não sei o que fazer com o dinheiro.",
    "objetivo": "Decidir onde reaplicar sem perder a segurança.",
    "prazo": "O vencimento é em 9 dias.",
    "mudancas": "Pretendo comprar um apartamento em dois anos.",
}
_CONTEXTS = {
    "Camila Prates": build_meeting_context(
        {k: ContextAnswer(key=k, question=INTAKE_QUESTIONS[k], answer=a) for k, a in _CAMILA_ANSWERS.items()}
    )
}



def _seed_meetings(client_ids: dict[str, int]) -> None:
    scheduling = get_scheduling_service()
    slots = scheduling.find_free_slots(ADVISOR_ID, limit=len(_MEETINGS))
    for (name, topic, initiated_by, confirmed), slot in zip(_MEETINGS, slots):
        if name not in client_ids:
            continue
        meeting = scheduling.schedule(
            MeetingRequest(
                client_id=client_ids[name],
                advisor_id=ADVISOR_ID,
                preferred=slot,
                topic=topic,
                initiated_by=initiated_by,
                context=_CONTEXTS.get(name),
            )
        )
        if confirmed:
            # Quem confirma é a parte que não pediu.
            if initiated_by == MeetingParty.ADVISOR:
                scheduling.confirm(meeting.id, meeting.client_id, MeetingParty.CLIENT)
            else:
                scheduling.confirm(meeting.id, meeting.advisor_id, MeetingParty.ADVISOR)
