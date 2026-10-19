from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel


class Sentiment(StrEnum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


class Quote(BaseModel):
    ticker: str
    price: Decimal
    change_pct: Decimal
    timestamp: datetime


class NewsItem(BaseModel):
    source: str
    title: str
    summary: str = ""
    url: str = ""
    published_at: datetime
    related_tickers: list[str] = []
    sentiment: Sentiment = Sentiment.NEUTRAL


class CurrencyRate(BaseModel):
    code: str
    name: str
    value: Decimal
    variation_pct: Decimal = Decimal("0")
    updated_at: datetime
