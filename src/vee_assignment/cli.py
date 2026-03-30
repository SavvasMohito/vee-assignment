from __future__ import annotations

import uuid

from langchain_core.messages import HumanMessage

from vee_assignment.config import Settings
from vee_assignment.graph.post_creation import build_post_creation_graph

PLATFORMS = {"linkedin", "instagram", "x"}


def main() -> None:
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        print("Expected required env vars: OPENAI_API_KEY, JINA_API_KEY")
        return

    organization_name = input("Organization name: ").strip()
    organization_url = input("Organization website URL (optional): ").strip()
    platform = _read_platform()

    graph = build_post_creation_graph(settings)
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    print("\nPost creation assistant ready. Type 'exit' to stop.\n")
    while True:
        user_request = input("You: ").strip()
        if user_request.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break
        if not user_request:
            continue

        try:
            state = graph.invoke(
                {
                    "messages": [HumanMessage(content=user_request)],
                    "organization_name": organization_name,
                    "organization_url": organization_url,
                    "platform": platform,
                },
                config=config,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Assistant error: {exc}\n")
            continue

        messages = state.get("messages", [])
        if not messages:
            print("Assistant: Unable to produce a response.\n")
            continue
        print(f"Assistant:\n{messages[-1].content}\n")


def _read_platform() -> str:
    while True:
        platform = input("Target platform (linkedin / instagram / x): ").strip().lower()
        if platform in PLATFORMS:
            return platform
        print("Unsupported platform. Choose one of: linkedin, instagram, x.")


if __name__ == "__main__":
    main()
