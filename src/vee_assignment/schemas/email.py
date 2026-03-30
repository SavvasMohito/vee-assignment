from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EmailCategory = Literal[
    "Donation Thank You Email",
    "Inform about Volunteering Opportunities",
    "Ask Availability for a Meeting",
]


class EmailCategoryDecision(BaseModel):
    category: EmailCategory
    fits_allowed_categories: bool
    reasoning: str = Field(min_length=1)


class EmailDraft(BaseModel):
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class EmailReviewResult(BaseModel):
    final_subject: str = Field(min_length=1)
    final_body: str = Field(min_length=1)
    risk_notes: list[str] = Field(default_factory=list)
    changes_made: str = Field(min_length=1)
