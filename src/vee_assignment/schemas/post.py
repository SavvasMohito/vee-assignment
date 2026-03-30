from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Platform = Literal["linkedin", "instagram", "x"]
Pillar = Literal[
    "Impact & Mission",
    "Education & Awareness",
    "Community & Events",
    "Fundraising & Donations",
    "People & Culture",
]


class SearchPlan(BaseModel):
    search_query: str = Field(min_length=5)
    rationale: str = Field(min_length=1)


class PillarDecision(BaseModel):
    pillar: Pillar
    reasoning: str = Field(min_length=1)


class PostDraft(BaseModel):
    post_text: str = Field(min_length=1)
    hashtags: list[str] = Field(default_factory=list, max_length=6)
    rationale: str = Field(min_length=1)


class ReviewResult(BaseModel):
    final_post_text: str = Field(min_length=1)
    risk_notes: list[str] = Field(default_factory=list)
    changes_made: str = Field(min_length=1)


class PostRequirementDecision(BaseModel):
    enough_info: bool
    extracted_platform: Platform | None = None
    extracted_topic: str = ""
    prefers_suggestion: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    followup_question: str = Field(min_length=1)
    reasoning: str = Field(min_length=1)
