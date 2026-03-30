from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage

from vee_assignment.config import Settings
from vee_assignment.graph.assistant import build_assistant_graph


@dataclass
class AssistantEvalTarget:
    settings: Settings

    def __post_init__(self) -> None:
        self.graph = build_assistant_graph(self.settings)

    def __call__(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Run one eval example through the assistant graph."""
        user_message = str(inputs.get("user_message", "")).strip()
        organization_url = str(inputs.get("organization_url", "")).strip()
        organization_name = str(inputs.get("organization_name", "")).strip() or "the organization"
        org_profile_note = str(inputs.get("org_profile_note", "")).strip()

        state = self.graph.invoke(
            {
                "messages": [HumanMessage(content=user_message)],
                "organization_url": organization_url,
                "organization_name": organization_name,
                "org_profile_note": org_profile_note,
            },
            config={"configurable": {"thread_id": str(uuid.uuid4())}},
        )

        messages = state.get("messages", [])
        response_text = str(messages[-1].content) if messages else ""
        source_urls = state.get("source_urls", [])
        qa_source_urls = state.get("qa_source_urls", [])

        return {
            "route": state.get("route", ""),
            "response_text": response_text,
            "platform": state.get("platform", ""),
            "email_category": state.get("email_category", ""),
            "selected_pillar": state.get("selected_pillar", ""),
            "source_urls_count": len(source_urls) + len(qa_source_urls),
            "source_urls": list(dict.fromkeys([*source_urls, *qa_source_urls]))[:5],
        }
