# Vee Assignment - LangGraph Post Creation

This project implements the first feature from `assignment.md`: a conversational post-creation assistant for nonprofits using LangGraph + LangChain with OpenAI models and Jina web research.

## Implemented Scope

- Conversational CLI flow for social post creation.
- LangGraph workflow with explicit state and node boundaries.
- Internet research via `s.jina.ai` search with full SERP context.
- Automatic content pillar selection (from the 5 required pillars).
- Platform-adapted post drafting for LinkedIn, Instagram, and X.
- Review node to reduce risky/fabricated claims.

## Tech Stack

- Python 3.13+
- `uv` for dependency and environment management
- LangGraph (graph orchestration)
- LangChain + `langchain-openai` (LLM integration)
- OpenAI models via `OPENAI_API_KEY`
- Jina AI search endpoint (`s.jina.ai`) for SERP + linked context

## Setup

1. Install dependencies:

```bash
uv sync
```

1. Create env file:

```bash
cp .env.example .env
```

1. Add required keys in `.env`:

- `OPENAI_API_KEY`
- `JINA_API_KEY`

Optional:

- `OPENAI_MODEL` (default `gpt-4.1-mini`)
- `REQUEST_TIMEOUT_SECONDS`

## Run

Use the project script:

```bash
uv run vee-assignment
```

Or run directly:

```bash
uv run python main.py
```

The CLI will prompt for:

- Organization website URL
- Target platform (`linkedin`, `instagram`, `x`)

Then you can chat with requests like:

- "Write a post about the flooding in Texas."
- "Create an Instagram post about volunteer cleanup day."

Type `exit` to quit.

## Architecture (First Feature)

The post-creation flow is a LangGraph `StateGraph`:

1. **Intake** - classify whether the request is a post-creation request.
2. **Search plan** - generate a focused web query.
3. **Organization profile** - scrape website and infer organization name.
4. **Research** - fetch full SERP context using `s.jina.ai`.
5. **Summarize** - condense research into high-confidence notes.
6. **Pillar selection** - choose one required NPO pillar.
7. **Draft** - generate platform-specific post + hashtags.
8. **Review** - safety/quality review and adjustment.
9. **Finalize** - return formatted response with cited sources.

Key files:

- `src/vee_assignment/config.py`
- `src/vee_assignment/tools/jina.py`
- `src/vee_assignment/graph/post_creation.py`
- `src/vee_assignment/cli.py`

## Notes for Next Milestones

The project is structured so email drafting and organization Q&A can be added as additional graph flows without changing the config/tooling foundation.
