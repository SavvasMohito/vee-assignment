from __future__ import annotations

import httpx
from langchain_core.messages import AIMessage

from vee_assignment.graph.state import AssistantState
from vee_assignment.prompts.qa import QA_ANSWER_PROMPT, QA_SCOPE_PROMPT, QA_SEARCH_PLAN_PROMPT
from vee_assignment.prompts.router import SYSTEM_PROMPT
from vee_assignment.tools.jina import JinaClient


def route_after_qa_scope(state: AssistantState) -> str:
    if state.get("qa_scope_allowed"):
        return "answerable"
    return "out_of_scope"


def create_qa_nodes(
    jina: JinaClient,
    qa_scope_model,
    qa_search_plan_model,
    qa_answer_model,
) -> dict[str, object]:
    """Build organization QA subgraph node callables."""

    def analyze_qa_scope_node(state: AssistantState) -> AssistantState:
        user_request = state.get("user_request", "")
        decision = qa_scope_model.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": QA_SCOPE_PROMPT.format(
                        organization_name=state.get("organization_name", ""),
                        organization_url=state.get("organization_url", ""),
                        user_request=user_request,
                    ),
                },
            ]
        )
        return {
            "qa_question": user_request,
            "qa_scope_allowed": bool(decision.organization_related and decision.answerable_with_public_context),
            "qa_scope_reasoning": decision.reasoning,
            "qa_followup_or_redirect": decision.followup_or_redirect,
        }

    def qa_out_of_scope_node(state: AssistantState) -> AssistantState:
        message = state.get("qa_followup_or_redirect", "").strip() or (
            "I can help with questions about your organization and its public activities, " "but I can't answer that question."
        )
        return {"messages": [AIMessage(content=message)]}

    def plan_qa_search_node(state: AssistantState) -> AssistantState:
        question = state.get("qa_question", state.get("user_request", ""))
        planned = qa_search_plan_model.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": QA_SEARCH_PLAN_PROMPT.format(
                        organization_name=state.get("organization_name", ""),
                        organization_url=state.get("organization_url", ""),
                        qa_question=question,
                    ),
                },
            ]
        )
        return {"qa_search_query": planned.search_query, "qa_search_rationale": planned.rationale}

    def retrieve_qa_context_node(state: AssistantState) -> AssistantState:
        organization_url = state.get("organization_url", "")
        question = state.get("qa_question", state.get("user_request", ""))
        query = state.get("qa_search_query", question)

        website_context = ""
        warning = ""
        try:
            if organization_url:
                website_context = jina.fetch_url_content(organization_url)[:5000]
        except httpx.HTTPError as exc:
            warning = f"Website scraping failed ({exc.__class__.__name__})."

        try:
            docs = jina.collect_research(query=query, max_pages=3)
        except httpx.HTTPError as exc:
            docs = []
            warning = (warning + " " if warning else "") + f"Web research failed ({exc.__class__.__name__})."

        material = [{"url": doc.url, "content": doc.content} for doc in docs]
        urls: list[str] = []
        for doc in docs:
            urls.extend(jina.extract_urls(doc.content))
        deduped_urls = list(dict.fromkeys(urls))[:5]

        return {
            "qa_website_context": website_context,
            "qa_research_documents": material,
            "qa_source_urls": deduped_urls,
            "qa_warning": warning.strip(),
        }

    def draft_qa_answer_node(state: AssistantState) -> AssistantState:
        docs = state.get("qa_research_documents", [])
        if docs:
            qa_research_blob = "\n\n".join(f"Source: {item['url']}\n{item['content'][:1200]}" for item in docs)
        else:
            qa_research_blob = "No web research documents were retrieved."

        drafted = qa_answer_model.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": QA_ANSWER_PROMPT.format(
                        organization_name=state.get("organization_name", ""),
                        organization_url=state.get("organization_url", ""),
                        qa_question=state.get("qa_question", state.get("user_request", "")),
                        qa_website_context=state.get("qa_website_context", "No website context available."),
                        qa_research_blob=qa_research_blob,
                    ),
                },
            ]
        )
        source_urls = drafted.source_urls or state.get("qa_source_urls", [])
        return {
            "qa_answer": drafted.answer,
            "qa_source_urls": source_urls[:5],
            "qa_warning": drafted.caution_note or state.get("qa_warning", ""),
        }

    def finalize_qa_answer_node(state: AssistantState) -> AssistantState:
        sources = state.get("qa_source_urls", [])
        source_block = "\n".join(f"- {url}" for url in sources) if sources else "- No direct public source URLs captured."
        warning = state.get("qa_warning", "").strip()

        content = state.get("qa_answer", "")
        if warning:
            content = f"{content}\n\nNote: {warning}"
        content = f"{content}\n\nSources:\n{source_block}"
        return {"messages": [AIMessage(content=content)]}

    return {
        "analyze_qa_scope": analyze_qa_scope_node,
        "qa_out_of_scope": qa_out_of_scope_node,
        "plan_qa_search": plan_qa_search_node,
        "retrieve_qa_context": retrieve_qa_context_node,
        "draft_qa_answer": draft_qa_answer_node,
        "finalize_qa_answer": finalize_qa_answer_node,
    }
