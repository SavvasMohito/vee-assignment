from __future__ import annotations

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from vee_assignment.graph.state import AssistantState
from vee_assignment.prompts.email import EMAIL_CATEGORY_PROMPT, EMAIL_DRAFT_PROMPT, EMAIL_REVIEW_PROMPT


def route_after_email_category(state: AssistantState) -> str:
    if state.get("email_fits_allowed_categories"):
        return "supported"
    return "unsupported"


def create_email_nodes(
    model: ChatOpenAI,
    system_prompt: str,
    email_category_model,
    email_draft_model,
    email_review_model,
) -> dict[str, object]:
    """Build email-draft subgraph node callables."""

    def classify_email_category_node(state: AssistantState) -> AssistantState:
        extracted_category = state.get("email_extracted_category", "").strip()
        if extracted_category:
            return {
                "email_category": extracted_category,
                "email_category_reasoning": "Used category extracted by email requirements analyzer.",
                "email_fits_allowed_categories": state.get("email_category_supported", True),
            }

        decision = email_category_model.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": EMAIL_CATEGORY_PROMPT.format(user_request=state.get("user_request", ""))},
            ]
        )
        return {
            "email_category": decision.category,
            "email_category_reasoning": decision.reasoning,
            "email_fits_allowed_categories": decision.fits_allowed_categories,
        }

    def unsupported_email_node(state: AssistantState) -> AssistantState:
        content = (
            "I can draft emails only in these categories:\n"
            "- Donation Thank You Email\n"
            "- Inform about Volunteering Opportunities\n"
            "- Ask Availability for a Meeting (with meeting scope)\n\n"
            "Please rephrase your request for one of these."
        )
        return {"messages": [AIMessage(content=content)]}

    def draft_email_node(state: AssistantState) -> AssistantState:
        drafted = email_draft_model.invoke(
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": EMAIL_DRAFT_PROMPT.format(
                        organization_name=state.get("organization_name", "the organization"),
                        organization_url=state.get("organization_url", ""),
                        email_category=state.get("email_category", ""),
                        user_request=state.get("user_request", ""),
                    ),
                },
            ]
        )
        return {
            "email_subject": drafted.subject,
            "email_body": drafted.body,
            "email_rationale": drafted.rationale,
        }

    def review_email_node(state: AssistantState) -> AssistantState:
        reviewed = email_review_model.invoke(
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": EMAIL_REVIEW_PROMPT.format(
                        email_category=state.get("email_category", ""),
                        subject=state.get("email_subject", ""),
                        body=state.get("email_body", ""),
                    ),
                },
            ]
        )
        return {
            "email_final_subject": reviewed.final_subject,
            "email_final_body": reviewed.final_body,
            "email_risk_notes": reviewed.risk_notes,
            "email_review_changes": reviewed.changes_made,
        }

    def finalize_email_node(state: AssistantState) -> AssistantState:
        notes = state.get("email_risk_notes", [])
        notes_block = "\n".join(f"- {note}" for note in notes) if notes else "- None"
        content = (
            f"Email Category: {state.get('email_category', 'Unknown')}\n"
            f"Subject: {state.get('email_final_subject', '')}\n\n"
            f"{state.get('email_final_body', '')}\n\n"
            "Review notes:\n"
            f"{notes_block}"
        )
        return {"messages": [AIMessage(content=content)]}

    return {
        "classify_email_category": classify_email_category_node,
        "unsupported_email": unsupported_email_node,
        "draft_email": draft_email_node,
        "review_email": review_email_node,
        "finalize_email": finalize_email_node,
    }
