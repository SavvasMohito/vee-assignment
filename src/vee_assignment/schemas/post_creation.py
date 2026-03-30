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


class IntentDecision(BaseModel):
    is_post_request: bool
    reasoning: str = Field(min_length=1)


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


class OrganizationProfile(BaseModel):
    organization_name: str = Field(min_length=1)
    confidence_note: str = Field(min_length=1)
