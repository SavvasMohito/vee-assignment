from __future__ import annotations

import uuid
from typing import Any

from langchain_core.messages import HumanMessage

from vee_assignment.config import Settings
from vee_assignment.graph.assistant import build_assistant_graph, load_organization_profile


def main() -> None:
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        print("Expected required env vars: OPENAI_API_KEY, JINA_API_KEY")
        return

    print(
        "Maggie: Hey, I am Maggie. I can help you create social posts, "
        "draft supported nonprofit emails, and answer general questions about "
        "your organization."
    )
    print(
        "Maggie: Before I start, please share your organization's website so "
        "I can understand your profile and help with better context.\n"
    )
    organization_url = _read_organization_url()

    print("\nMaggie: Thanks. Give me a moment to learn about your organization.\n")
    profile = load_organization_profile(settings, organization_url)
    organization_name = profile.get("organization_name", "your organization")

    graph = build_assistant_graph(settings)
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    print(f"Maggie: Thanks, I have the context I need for {organization_name}. " "What would you like help with today?")
    print("Maggie: I can help with social posts, email drafting, and answering general questions about your organization.\n")
    while True:
        user_request = input("You: ").strip()
        if user_request.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break
        if not user_request:
            continue

        input_state = {
            "messages": [HumanMessage(content=user_request)],
            "organization_url": organization_url,
            "organization_name": organization_name,
            "org_profile_note": profile.get("org_profile_note", ""),
        }
        try:
            state = _invoke_with_optional_stream(graph, input_state, config, settings)
        except Exception as exc:  # noqa: BLE001
            print(f"Assistant error: {exc}\n")
            continue

        messages = state.get("messages", [])
        if not messages:
            print("Maggie: Unable to produce a response.\n")
            continue
        print(f"Maggie:\n{messages[-1].content}\n")


def _read_organization_url() -> str:
    while True:
        value = input("Organization website URL: ").strip()
        if value.startswith("http://") or value.startswith("https://"):
            return value
        print("Please provide a full URL starting with http:// or https://")


def _invoke_with_optional_stream(
    graph: Any,
    input_state: dict[str, Any],
    config: dict[str, Any],
    settings: Settings,
) -> dict[str, Any]:
    if not settings.enable_observability_stream:
        return graph.invoke(input_state, config=config)

    for part in graph.stream(
        input_state,
        config=config,
        stream_mode="updates",
        version="v2",
    ):
        if part.get("type") != "updates":
            continue
        updates = part.get("data", {})
        for node_name, update in updates.items():
            _print_trace_update(settings.observability_stream_prefix, node_name, update)

    snapshot = graph.get_state(config)
    return snapshot.values


def _print_trace_update(prefix: str, node_name: str, update: Any) -> None:
    if isinstance(update, dict) and update:
        keys = ", ".join(sorted(update.keys()))
        print(f"{prefix} {node_name} updated ({keys})")
        return
    print(f"{prefix} {node_name} updated")


if __name__ == "__main__":
    main()
