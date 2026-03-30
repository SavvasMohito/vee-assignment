from __future__ import annotations

import httpx
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from vee_assignment.config import Settings
from vee_assignment.graph.email_flow import create_email_nodes, route_after_email_category
from vee_assignment.graph.post_flow import create_post_nodes
from vee_assignment.graph.state import AssistantState
from vee_assignment.prompts.email import EMAIL_REQUIREMENTS_PROMPT
from vee_assignment.prompts.post import POST_REQUIREMENTS_PROMPT
from vee_assignment.prompts.router import ORG_NAME_PROMPT, ROUTER_PROMPT, SYSTEM_PROMPT
from vee_assignment.schemas.email import EmailCategoryDecision, EmailDraft, EmailRequirementDecision, EmailReviewResult
from vee_assignment.schemas.post import PillarDecision, PostDraft, PostRequirementDecision, ReviewResult, SearchPlan
from vee_assignment.schemas.router import OrganizationProfile, RouteDecision
from vee_assignment.tools.jina import JinaClient


def build_assistant_graph(settings: Settings):
    model = ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key)
    jina = JinaClient(
        api_key=settings.jina_api_key,
        timeout_seconds=settings.request_timeout_seconds,
    )

    router_model = model.with_structured_output(RouteDecision)
    post_requirements_model = model.with_structured_output(PostRequirementDecision)
    email_requirements_model = model.with_structured_output(EmailRequirementDecision)
    plan_model = model.with_structured_output(SearchPlan)
    pillar_model = model.with_structured_output(PillarDecision)
    post_draft_model = model.with_structured_output(PostDraft)
    post_review_model = model.with_structured_output(ReviewResult)
    email_category_model = model.with_structured_output(EmailCategoryDecision)
    email_draft_model = model.with_structured_output(EmailDraft)
    email_review_model = model.with_structured_output(EmailReviewResult)

    post_nodes = create_post_nodes(
        model=model,
        jina=jina,
        plan_model=plan_model,
        pillar_model=pillar_model,
        post_draft_model=post_draft_model,
        post_review_model=post_review_model,
    )
    email_nodes = create_email_nodes(
        model=model,
        email_category_model=email_category_model,
        email_draft_model=email_draft_model,
        email_review_model=email_review_model,
    )

    def infer_org_profile_node(state: AssistantState) -> AssistantState:
        if state.get("organization_name"):
            return {}
        organization_url = state.get("organization_url", "").strip()
        return _infer_organization_profile(model, jina, organization_url)

    def router_node(state: AssistantState) -> AssistantState:
        user_request = _latest_user_message(state)
        if state.get("awaiting_post_requirements"):
            merged_request = _merge_clarification(state.get("pending_post_request", ""), user_request)
            return {
                "user_request": merged_request,
                "route": "post",
                "route_reasoning": "Merged post clarification and re-checking requirements.",
                "awaiting_post_requirements": False,
                "pending_post_request": merged_request,
            }
        if state.get("awaiting_email_requirements"):
            merged_request = _merge_clarification(state.get("pending_email_request", ""), user_request)
            return {
                "user_request": merged_request,
                "route": "email",
                "route_reasoning": "Merged email clarification and re-checking requirements.",
                "awaiting_email_requirements": False,
                "pending_email_request": merged_request,
            }

        decision = router_model.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": ROUTER_PROMPT.format(user_message=user_request)},
            ]
        )
        return {
            "user_request": user_request,
            "route": decision.route,
            "route_reasoning": decision.reasoning,
        }

    def route_after_router(state: AssistantState) -> str:
        route = state.get("route", "other")
        if route in {"post", "email", "qa", "other"}:
            return route
        return "other"

    def analyze_post_requirements_node(state: AssistantState) -> AssistantState:
        decision = post_requirements_model.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": POST_REQUIREMENTS_PROMPT.format(
                        organization_name=state.get("organization_name", ""),
                        organization_url=state.get("organization_url", ""),
                        user_request=state.get("user_request", ""),
                        known_platform=state.get("platform", ""),
                    ),
                },
            ]
        )
        platform = decision.extracted_platform or state.get("platform", "")
        return {
            "platform": platform,
            "post_info_sufficient": decision.enough_info,
            "post_missing_fields": decision.missing_fields,
            "post_followup_question": decision.followup_question,
            "post_extracted_topic": decision.extracted_topic,
            "post_extracted_platform": decision.extracted_platform or "",
            "post_user_prefers_suggestion": decision.prefers_suggestion,
            "pending_post_request": state.get("user_request", ""),
        }

    def route_after_post_requirements(state: AssistantState) -> str:
        if state.get("post_info_sufficient"):
            return "ready"
        return "needs_info"

    def ask_post_requirements_node(state: AssistantState) -> AssistantState:
        message = state.get("post_followup_question", "").strip() or (
            "Before I draft, do you have a specific topic in mind, or should I suggest "
            "one from the latest news about your organization?"
        )
        return {
            "messages": [AIMessage(content=message)],
            "awaiting_post_requirements": True,
            "pending_post_request": state.get("pending_post_request", state.get("user_request", "")),
        }

    def analyze_email_requirements_node(state: AssistantState) -> AssistantState:
        decision = email_requirements_model.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": EMAIL_REQUIREMENTS_PROMPT.format(user_request=state.get("user_request", ""))},
            ]
        )
        return {
            "email_info_sufficient": decision.enough_info,
            "email_missing_fields": decision.missing_fields,
            "email_followup_question": decision.followup_question,
            "email_extracted_category": decision.extracted_category or "",
            "email_extracted_details": decision.extracted_details,
            "email_category_supported": decision.category_supported,
            "pending_email_request": state.get("user_request", ""),
            "email_category": decision.extracted_category or state.get("email_category", ""),
            "email_fits_allowed_categories": decision.category_supported,
        }

    def route_after_email_requirements(state: AssistantState) -> str:
        if not state.get("email_category_supported", True):
            return "unsupported"
        if state.get("email_info_sufficient"):
            return "ready"
        return "needs_info"

    def ask_email_requirements_node(state: AssistantState) -> AssistantState:
        message = state.get("email_followup_question", "").strip() or (
            "Before I draft, what should this email include? I can help with Donation Thank You, "
            "Volunteering Opportunities, and Meeting Availability emails."
        )
        return {
            "messages": [AIMessage(content=message)],
            "awaiting_email_requirements": True,
            "pending_email_request": state.get("pending_email_request", state.get("user_request", "")),
        }

    def qa_not_implemented_node(state: AssistantState) -> AssistantState:
        message = (
            "Sorry, I can't help with organization Q&A just yet. "
            "For now, I can help you create social posts and draft emails "
            "in the 3 supported categories."
        )
        return {"messages": [AIMessage(content=message)]}

    def capabilities_help_node(state: AssistantState) -> AssistantState:
        message = (
            "Sorry, I can't help with that. If you'd like, I can help you create "
            "social media posts, draft one of the 3 supported email types, or soon "
            "answer questions about your organization."
        )
        return {"messages": [AIMessage(content=message)]}

    graph_builder = StateGraph(AssistantState)
    graph_builder.add_node("infer_org_profile", infer_org_profile_node)
    graph_builder.add_node("router", router_node)
    graph_builder.add_node("analyze_post_requirements", analyze_post_requirements_node)
    graph_builder.add_node("ask_post_requirements", ask_post_requirements_node)
    graph_builder.add_node("analyze_email_requirements", analyze_email_requirements_node)
    graph_builder.add_node("ask_email_requirements", ask_email_requirements_node)
    graph_builder.add_node("qa_not_implemented", qa_not_implemented_node)
    graph_builder.add_node("capabilities_help", capabilities_help_node)

    for name, fn in post_nodes.items():
        graph_builder.add_node(name, fn)
    for name, fn in email_nodes.items():
        graph_builder.add_node(name, fn)

    graph_builder.add_edge(START, "infer_org_profile")
    graph_builder.add_edge("infer_org_profile", "router")
    graph_builder.add_conditional_edges(
        "router",
        route_after_router,
        {
            "post": "analyze_post_requirements",
            "email": "analyze_email_requirements",
            "qa": "qa_not_implemented",
            "other": "capabilities_help",
        },
    )

    graph_builder.add_conditional_edges(
        "analyze_post_requirements",
        route_after_post_requirements,
        {"ready": "search_plan", "needs_info": "ask_post_requirements"},
    )
    graph_builder.add_conditional_edges(
        "analyze_email_requirements",
        route_after_email_requirements,
        {"ready": "classify_email_category", "needs_info": "ask_email_requirements", "unsupported": "unsupported_email"},
    )

    graph_builder.add_edge("ask_post_requirements", END)
    graph_builder.add_edge("ask_email_requirements", END)
    graph_builder.add_edge("qa_not_implemented", END)
    graph_builder.add_edge("capabilities_help", END)

    graph_builder.add_edge("search_plan", "research")
    graph_builder.add_edge("research", "summarize_research")
    graph_builder.add_edge("summarize_research", "select_pillar")
    graph_builder.add_edge("select_pillar", "draft_post")
    graph_builder.add_edge("draft_post", "review_post")
    graph_builder.add_edge("review_post", "finalize_post")
    graph_builder.add_edge("finalize_post", END)

    graph_builder.add_conditional_edges(
        "classify_email_category",
        route_after_email_category,
        {"supported": "draft_email", "unsupported": "unsupported_email"},
    )
    graph_builder.add_edge("unsupported_email", END)
    graph_builder.add_edge("draft_email", "review_email")
    graph_builder.add_edge("review_email", "finalize_email")
    graph_builder.add_edge("finalize_email", END)

    return graph_builder.compile(checkpointer=InMemorySaver())


def build_post_creation_graph(settings: Settings):
    """Backward-compatible alias for the unified assistant graph."""
    return build_assistant_graph(settings)


def load_organization_profile(settings: Settings, organization_url: str) -> dict[str, str]:
    model = ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key)
    jina = JinaClient(
        api_key=settings.jina_api_key,
        timeout_seconds=settings.request_timeout_seconds,
    )
    return _infer_organization_profile(model, jina, organization_url)


def _latest_user_message(state: AssistantState) -> str:
    messages = state.get("messages", [])
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content)
    return ""


def _merge_clarification(previous_request: str, clarification: str) -> str:
    base = previous_request.strip()
    extra = clarification.strip()
    if not base:
        return extra
    if not extra:
        return base
    return f"{base}\n\nUser clarification: {extra}"


def _infer_organization_profile(
    model: ChatOpenAI,
    jina: JinaClient,
    organization_url: str,
) -> dict[str, str]:
    organization_url = organization_url.strip()
    if not organization_url:
        return {"organization_name": "the organization", "org_profile_note": "No organization URL provided."}

    try:
        website_content = jina.fetch_url_content(organization_url)
    except httpx.HTTPError:
        domain_fallback = organization_url.replace("https://", "").replace("http://", "").split("/")[0]
        return {
            "organization_name": domain_fallback or "the organization",
            "org_profile_note": "Could not scrape organization website; used URL domain as fallback.",
        }

    inferred = model.with_structured_output(OrganizationProfile).invoke(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": ORG_NAME_PROMPT.format(
                    organization_url=organization_url,
                    website_content=website_content[:4000],
                ),
            },
        ]
    )
    return {"organization_name": inferred.organization_name, "org_profile_note": inferred.confidence_note}
