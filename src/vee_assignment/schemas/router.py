from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RouteIntent = Literal["post", "email", "qa", "other"]


class RouteDecision(BaseModel):
    route: RouteIntent
    reasoning: str = Field(min_length=1)


class OrganizationProfile(BaseModel):
    organization_name: str = Field(min_length=1)
    confidence_note: str = Field(min_length=1)
