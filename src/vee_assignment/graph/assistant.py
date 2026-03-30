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
from vee_assignment.prompts.router import ORG_NAME_PROMPT, ROUTER_PROMPT, SYSTEM_PROMPT
from vee_assignment.schemas.email import EmailCategoryDecision, EmailDraft, EmailReviewResult
from vee_assignment.schemas.post import PillarDecision, PostDraft, ReviewResult, SearchPlan
from vee_assignment.schemas.router import OrganizationProfile, RouteDecision
from vee_assignment.tools.jina import JinaClient


def build_assistant_graph(settings: Settings):
    model = ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key)
    jina = JinaClient(
        api_key=settings.jina_api_key,
        timeout_seconds=settings.request_timeout_seconds,
    )

    router_model = model.with_structured_output(RouteDecision)
    org_profile_model = model.with_structured_output(OrganizationProfile)
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

        inferred = org_profile_model.invoke(
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

    def router_node(state: AssistantState) -> AssistantState:
        user_request = _latest_user_message(state)
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

    def qa_not_implemented_node(state: AssistantState) -> AssistantState:
        message = (
            "Organization Q&A is planned next. I can currently help with:\n"
            "- social media post creation\n"
            "- drafting emails in the 3 supported categories"
        )
        return {"messages": [AIMessage(content=message)]}

    def capabilities_help_node(state: AssistantState) -> AssistantState:
        message = (
            "I can help with:\n"
            "1) Social media post creation (LinkedIn, Instagram, X)\n"
            "2) Email drafting for:\n"
            "   - Donation Thank You Email\n"
            "   - Inform about Volunteering Opportunities\n"
            "   - Ask Availability for a Meeting (with meeting scope)\n"
            "3) Organization Q&A (coming next milestone)\n\n"
            "Try: 'Draft a thank-you email for recent donors.'"
        )
        return {"messages": [AIMessage(content=message)]}

    graph_builder = StateGraph(AssistantState)
    graph_builder.add_node("infer_org_profile", infer_org_profile_node)
    graph_builder.add_node("router", router_node)
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
            "post": "search_plan",
            "email": "classify_email_category",
            "qa": "qa_not_implemented",
            "other": "capabilities_help",
        },
    )

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


def _latest_user_message(state: AssistantState) -> str:
    messages = state.get("messages", [])
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content)
    return ""
