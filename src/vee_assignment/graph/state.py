from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class AssistantState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    organization_name: str
    organization_url: str
    platform: str
    awaiting_post_requirements: bool
    pending_post_request: str
    awaiting_email_requirements: bool
    pending_email_request: str
    route: str
    route_reasoning: str
    user_request: str
    org_profile_note: str

    # LLM requirement-gating keys.
    post_info_sufficient: bool
    post_missing_fields: list[str]
    post_followup_question: str
    post_extracted_topic: str
    post_extracted_platform: str
    post_user_prefers_suggestion: bool
    email_info_sufficient: bool
    email_missing_fields: list[str]
    email_followup_question: str
    email_extracted_category: str
    email_extracted_details: str
    email_category_supported: bool

    # Post flow keys.
    search_query: str
    search_rationale: str
    research_documents: list[dict[str, str]]
    research_summary: str
    selected_pillar: str
    pillar_reasoning: str
    draft_post_text: str
    hashtags: list[str]
    draft_rationale: str
    final_post_text: str
    risk_notes: list[str]
    review_changes_made: str
    source_urls: list[str]
    research_warning: str

    # Email flow keys.
    email_category: str
    email_category_reasoning: str
    email_fits_allowed_categories: bool
    email_subject: str
    email_body: str
    email_rationale: str
    email_final_subject: str
    email_final_body: str
    email_risk_notes: list[str]
    email_review_changes: str
