from __future__ import annotations

from pydantic import BaseModel, Field


class QaScopeDecision(BaseModel):
    organization_related: bool
    answerable_with_public_context: bool
    reasoning: str = Field(min_length=1)
    followup_or_redirect: str = Field(min_length=1)


class QaSearchPlan(BaseModel):
    search_query: str = Field(min_length=5)
    rationale: str = Field(min_length=1)


class QaAnswer(BaseModel):
    answer: str = Field(min_length=1)
    source_urls: list[str] = Field(default_factory=list, max_length=5)
    caution_note: str = Field(default="")
