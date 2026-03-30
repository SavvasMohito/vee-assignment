from __future__ import annotations

import os
from pathlib import Path

from vee_assignment.config import Settings
from vee_assignment.graph.assistant import build_assistant_graph


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
PNG_PATH = DOCS_DIR / "assistant-workflow.png"
MERMAID_PATH = DOCS_DIR / "assistant-workflow.mmd"


def build_settings() -> Settings:
    """Build enough config to compile the graph without live API calls."""
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", "placeholder-openai-key"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        jina_api_key=os.getenv("JINA_API_KEY", "placeholder-jina-key"),
        request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20")),
        enable_observability_stream=False,
        observability_stream_prefix=os.getenv("OBSERVABILITY_STREAM_PREFIX", "[trace]"),
    )


def main() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    graph = build_assistant_graph(build_settings()).get_graph()
    MERMAID_PATH.write_text(graph.draw_mermaid(), encoding="utf-8")
    PNG_PATH.write_bytes(graph.draw_mermaid_png())

    print(f"Wrote Mermaid graph to {MERMAID_PATH}")
    print(f"Wrote PNG graph to {PNG_PATH}")


if __name__ == "__main__":
    main()
