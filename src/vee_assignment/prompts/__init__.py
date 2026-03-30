"""Prompt templates for router, post, email, and QA flows."""

from vee_assignment.prompts.email import (
    EMAIL_CATEGORY_PROMPT,
    EMAIL_DRAFT_PROMPT,
    EMAIL_REVIEW_PROMPT,
)
from vee_assignment.prompts.post import (
    DRAFT_PROMPT,
    PILLAR_PROMPT,
    RESEARCH_SUMMARY_PROMPT,
    REVIEW_PROMPT,
    SEARCH_PLAN_PROMPT,
)
from vee_assignment.prompts.qa import QA_ANSWER_PROMPT, QA_SCOPE_PROMPT, QA_SEARCH_PLAN_PROMPT
from vee_assignment.prompts.router import ORG_NAME_PROMPT, ROUTER_PROMPT, SYSTEM_PROMPT

__all__ = [
    "DRAFT_PROMPT",
    "EMAIL_CATEGORY_PROMPT",
    "EMAIL_DRAFT_PROMPT",
    "EMAIL_REVIEW_PROMPT",
    "ORG_NAME_PROMPT",
    "PILLAR_PROMPT",
    "QA_ANSWER_PROMPT",
    "QA_SCOPE_PROMPT",
    "QA_SEARCH_PLAN_PROMPT",
    "RESEARCH_SUMMARY_PROMPT",
    "REVIEW_PROMPT",
    "ROUTER_PROMPT",
    "SEARCH_PLAN_PROMPT",
    "SYSTEM_PROMPT",
]
