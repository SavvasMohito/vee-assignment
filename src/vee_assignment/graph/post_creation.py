from __future__ import annotations

from typing import Annotated, TypedDict

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph, add_messages

from vee_assignment.config import Settings
from vee_assignment.prompts.post_creation import (
    DRAFT_PROMPT,
    INTAKE_PROMPT,
    PILLAR_PROMPT,
    RESEARCH_SUMMARY_PROMPT,
    REVIEW_PROMPT,
    SEARCH_PLAN_PROMPT,
    SYSTEM_PROMPT,
)
from vee_assignment.schemas.post_creation import IntentDecision, PillarDecision, PostDraft, ReviewResult, SearchPlan
from vee_assignment.tools.jina import JinaClient


class PostCreationState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    organization_name: str
    organization_url: str
    platform: str
    user_request: str
    is_post_request: bool
    intent_reasoning: str
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


def build_post_creation_graph(settings: Settings):
    model = ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key)
    jina = JinaClient(
        api_key=settings.jina_api_key,
        timeout_seconds=settings.request_timeout_seconds,
        gl=settings.jina_gl,
        hl=settings.jina_hl,
    )

    intent_model = model.with_structured_output(IntentDecision)
    plan_model = model.with_structured_output(SearchPlan)
    pillar_model = model.with_structured_output(PillarDecision)
    draft_model = model.with_structured_output(PostDraft)
    review_model = model.with_structured_output(ReviewResult)

    def intake_node(state: PostCreationState) -> PostCreationState:
        user_request = _latest_user_message(state)
        decision = intent_model.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": INTAKE_PROMPT.format(user_message=user_request)},
            ]
        )
        return {
            "user_request": user_request,
            "is_post_request": decision.is_post_request,
            "intent_reasoning": decision.reasoning,
        }

    def route_after_intake(state: PostCreationState) -> str:
        if state.get("is_post_request"):
            return "continue"
        return "out_of_scope"

    def out_of_scope_node(state: PostCreationState) -> PostCreationState:
        message = (
            "I can currently help only with social media post creation. "
            "Try asking for a post request like: "
            "'Write a LinkedIn post about flooding in Texas for our nonprofit.'"
        )
        return {"messages": [AIMessage(content=message)]}

    def search_plan_node(state: PostCreationState) -> PostCreationState:
        planned = plan_model.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": SEARCH_PLAN_PROMPT.format(
                        organization_name=state.get("organization_name", ""),
                        organization_url=state.get("organization_url", ""),
                        platform=state.get("platform", ""),
                        user_request=state.get("user_request", ""),
                    ),
                },
            ]
        )
        return {"search_query": planned.search_query, "search_rationale": planned.rationale}

    def research_node(state: PostCreationState) -> PostCreationState:
        query = state.get("search_query", "")
        try:
            docs = jina.collect_research(query=query, max_pages=settings.max_research_pages)
        except httpx.HTTPError as exc:
            docs = []
            fallback = {
                "url": "research-error",
                "content": f"Research failed: {exc.__class__.__name__}",
            }
            return {
                "research_documents": [fallback],
                "source_urls": [],
                "research_warning": "Research retrieval failed. Output should be conservative.",
            }

        material = [{"url": doc.url, "content": doc.content} for doc in docs]
        sources: list[str] = []
        for doc in docs:
            sources.extend(jina.extract_urls(doc.content))
        deduped_sources = list(dict.fromkeys(sources))[: settings.max_research_pages]
        warning = ""
        if len(deduped_sources) == 0:
            warning = "Limited source extraction from web research."
        return {
            "research_documents": material,
            "source_urls": deduped_sources,
            "research_warning": warning,
        }

    def summarize_research_node(state: PostCreationState) -> PostCreationState:
        docs = state.get("research_documents", [])
        if not docs:
            return {"research_summary": "No reliable research sources were found. Use cautious, non-specific language."}

        research_blob = "\n\n".join(f"Source: {item['url']}\n{item['content'][:1500]}" for item in docs)
        summary = model.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": RESEARCH_SUMMARY_PROMPT.format(research_blob=research_blob),
                },
            ]
        )
        warning = state.get("research_warning", "")
        text = str(summary.content)
        if warning:
            text = f"{text}\n\nCaution: {warning}"
        return {"research_summary": text}

    def pillar_node(state: PostCreationState) -> PostCreationState:
        decision = pillar_model.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": PILLAR_PROMPT.format(
                        organization_name=state.get("organization_name", ""),
                        platform=state.get("platform", ""),
                        user_request=state.get("user_request", ""),
                        research_summary=state.get("research_summary", ""),
                    ),
                },
            ]
        )
        return {"selected_pillar": decision.pillar, "pillar_reasoning": decision.reasoning}

    def draft_node(state: PostCreationState) -> PostCreationState:
        drafted = draft_model.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": DRAFT_PROMPT.format(
                        organization_name=state.get("organization_name", ""),
                        organization_url=state.get("organization_url", ""),
                        platform=state.get("platform", ""),
                        pillar=state.get("selected_pillar", ""),
                        user_request=state.get("user_request", ""),
                        research_summary=state.get("research_summary", ""),
                    ),
                },
            ]
        )
        return {
            "draft_post_text": drafted.post_text,
            "hashtags": drafted.hashtags,
            "draft_rationale": drafted.rationale,
        }

    def review_node(state: PostCreationState) -> PostCreationState:
        reviewed = review_model.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": REVIEW_PROMPT.format(
                        post_text=state.get("draft_post_text", ""),
                        research_summary=state.get("research_summary", ""),
                    ),
                },
            ]
        )
        return {
            "final_post_text": reviewed.final_post_text,
            "risk_notes": reviewed.risk_notes,
            "review_changes_made": reviewed.changes_made,
        }

    def finalize_node(state: PostCreationState) -> PostCreationState:
        hashtags = " ".join(state.get("hashtags", []))
        sources = state.get("source_urls", [])
        source_block = (
            "\n".join(f"- {source}" for source in sources[:5])
            if sources
            else "- No direct sources captured; generated with cautious language."
        )
        risk_notes = state.get("risk_notes", [])
        risk_block = "\n".join(f"- {note}" for note in risk_notes) if risk_notes else "- None"

        content = (
            f"Platform: {state.get('platform', '').title()}\n"
            f"Pillar: {state.get('selected_pillar', 'Unknown')}\n\n"
            f"{state.get('final_post_text', '')}\n\n"
            f"{hashtags}\n\n"
            "Sources used:\n"
            f"{source_block}\n\n"
            "Review notes:\n"
            f"{risk_block}"
        )
        return {"messages": [AIMessage(content=content)]}

    graph_builder = StateGraph(PostCreationState)
    graph_builder.add_node("intake", intake_node)
    graph_builder.add_node("out_of_scope", out_of_scope_node)
    graph_builder.add_node("search_plan", search_plan_node)
    graph_builder.add_node("research", research_node)
    graph_builder.add_node("summarize_research", summarize_research_node)
    graph_builder.add_node("select_pillar", pillar_node)
    graph_builder.add_node("draft_post", draft_node)
    graph_builder.add_node("review_post", review_node)
    graph_builder.add_node("finalize", finalize_node)

    graph_builder.add_edge(START, "intake")
    graph_builder.add_conditional_edges(
        "intake",
        route_after_intake,
        {"continue": "search_plan", "out_of_scope": "out_of_scope"},
    )
    graph_builder.add_edge("out_of_scope", END)
    graph_builder.add_edge("search_plan", "research")
    graph_builder.add_edge("research", "summarize_research")
    graph_builder.add_edge("summarize_research", "select_pillar")
    graph_builder.add_edge("select_pillar", "draft_post")
    graph_builder.add_edge("draft_post", "review_post")
    graph_builder.add_edge("review_post", "finalize")
    graph_builder.add_edge("finalize", END)

    return graph_builder.compile(checkpointer=InMemorySaver())


def _latest_user_message(state: PostCreationState) -> str:
    messages = state.get("messages", [])
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content)
    return ""
