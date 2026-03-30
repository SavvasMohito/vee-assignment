from __future__ import annotations

import httpx
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from vee_assignment.graph.state import AssistantState
from vee_assignment.prompts.post import (
    DRAFT_PROMPT,
    PILLAR_PROMPT,
    RESEARCH_SUMMARY_PROMPT,
    REVIEW_PROMPT,
    SEARCH_PLAN_PROMPT,
)
from vee_assignment.prompts.router import SYSTEM_PROMPT
from vee_assignment.tools.jina import JinaClient


def create_post_nodes(
    model: ChatOpenAI,
    jina: JinaClient,
    plan_model,
    pillar_model,
    post_draft_model,
    post_review_model,
) -> dict[str, object]:
    """Build post-creation subgraph node callables."""

    def search_plan_node(state: AssistantState) -> AssistantState:
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

    def research_node(state: AssistantState) -> AssistantState:
        query = state.get("search_query", "")
        try:
            docs = jina.collect_research(query=query, max_pages=3)
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
        deduped_sources = list(dict.fromkeys(sources))[:3]
        warning = ""
        if len(deduped_sources) == 0:
            warning = "Limited source extraction from web research."
        return {
            "research_documents": material,
            "source_urls": deduped_sources,
            "research_warning": warning,
        }

    def summarize_research_node(state: AssistantState) -> AssistantState:
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

    def pillar_node(state: AssistantState) -> AssistantState:
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

    def draft_node(state: AssistantState) -> AssistantState:
        drafted = post_draft_model.invoke(
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

    def review_node(state: AssistantState) -> AssistantState:
        reviewed = post_review_model.invoke(
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

    def finalize_post_node(state: AssistantState) -> AssistantState:
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

    return {
        "search_plan": search_plan_node,
        "research": research_node,
        "summarize_research": summarize_research_node,
        "select_pillar": pillar_node,
        "draft_post": draft_node,
        "review_post": review_node,
        "finalize_post": finalize_post_node,
    }
