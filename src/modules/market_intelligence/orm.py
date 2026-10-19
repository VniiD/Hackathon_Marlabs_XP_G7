"""Notícias e sentimento. Cotações em tempo real ficam no Redis, não aqui."""

import datetime as dt

from sqlalchemy import BigInteger, Float, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


class NewsArticleRecord(Base):
    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)  # único: evita duplicar na coleta
    headline: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[dt.datetime]
    fetched_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    mentions: Mapped[list["NewsMentionRecord"]] = relationship(
        back_populates="article", cascade="all, delete-orphan", lazy="selectin"
    )


class NewsMentionRecord(Base):
    """Sentimento de uma notícia para um ativo (ou setor/macro: 'CAMBIO', 'BANCOS')."""

    __tablename__ = "news_mentions"

    news_id: Mapped[int] = mapped_column(
        ForeignKey("news_articles.id", ondelete="CASCADE"), primary_key=True
    )
    ticker: Mapped[str] = mapped_column(Text, primary_key=True)
    sentiment: Mapped[float] = mapped_column(Float(precision=24))  # REAL, de -1 a 1

    article: Mapped[NewsArticleRecord] = relationship(back_populates="mentions")
