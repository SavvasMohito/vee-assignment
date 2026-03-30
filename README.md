# Vee Assignment - Unified Conversational Agent

This project implements a unified conversational assistant for nonprofits using LangGraph + LangChain with OpenAI models and Jina-powered web/website retrieval.

## Implemented Scope

- One conversational CLI assistant with intent routing.
- LangGraph workflow with explicit state and node boundaries.
- Internet research via `s.jina.ai` for post context.
- Website scraping via `r.jina.ai` for organization grounding.
- Automatic content pillar selection (from the 5 required pillars).
- Platform-adapted post drafting for LinkedIn, Instagram, and X.
- Email drafting with only 3 allowed categories:
  - Donation Thank You Email
  - Inform about Volunteering Opportunities
  - Ask Availability for a Meeting (with meeting scope)
- Review node to reduce risky/fabricated claims.

## Tech Stack

- Python 3.13+
- `uv` for dependency and environment management
- LangGraph (graph orchestration)
- LangChain + `langchain-openai` (LLM integration)
- OpenAI models via `OPENAI_API_KEY`
- Jina AI search and reader endpoints (`s.jina.ai`, `r.jina.ai`)

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
- `ENABLE_OBSERVABILITY_STREAM` (default `false`) - print LangGraph node updates in terminal
- `OBSERVABILITY_STREAM_PREFIX` (default `[trace]`) - prefix for stream log lines

## Run

Use the project script:

```bash
uv run vee-assignment
```

Or run directly:

```bash
uv run python main.py
```

When the CLI starts, Maggie introduces herself, asks for the organization website URL, loads organization context for the session, and then invites the user to ask for help naturally.

Then you can chat with requests like:

- "Write a post about the flooding in Texas."
- "Create an Instagram post about volunteer cleanup day."
- "Draft a donation thank-you email for recent contributors."
- "Draft an email asking board members for meeting availability and include meeting scope."

Before drafting, Maggie uses an LLM requirement-check step to decide whether your request is specific enough.
If a post request is missing required context (platform and/or topic preference), Maggie asks a targeted follow-up question before creating content.
For email drafting, Maggie confirms one of the 3 supported email categories when needed and asks for missing details before drafting.
If you ask a direct question, Maggie routes it to an organization Q&A branch, checks whether the question is in-scope for org/public-context answers, and then responds using organization website context plus web research.

Type `exit` to quit.

## Observability (Bonus)

You can enable high-level LangGraph execution tracing in the CLI using streaming updates.

Set in `.env`:

```bash
ENABLE_OBSERVABILITY_STREAM=true
OBSERVABILITY_STREAM_PREFIX=[trace]
```

When enabled, the terminal prints concise internal progress lines such as:

```text
[trace] router updated (route, route_reasoning, user_request)
[trace] analyze_post_requirements updated (post_info_sufficient, post_followup_question)
[trace] ask_post_requirements updated (messages, awaiting_post_requirements)
```

This uses LangGraph `stream(..., stream_mode=\"updates\", version=\"v2\")` to show node-level state updates before Maggie's final reply.

### Traceability with LangSmith

If you set LangSmith environment variables, traces for model/tool/graph runs are also visible in the LangSmith UI:

- `LANGSMITH_API_KEY`
- `LANGSMITH_TRACING=true`
- `LANGSMITH_PROJECT=vee-assignment-evals` (or your preferred project name)

This complements terminal streaming by giving you persistent run history, debugging context, and experiment links.

## Evaluation (Bonus)

This repo includes a LangSmith-based evaluation harness for automated output checks across post, email, and QA branches.

### Evaluation Setup

Add these vars to `.env`:

- `LANGSMITH_API_KEY`
- `LANGSMITH_TRACING=true`
- `LANGSMITH_PROJECT=vee-assignment-evals` (or your preferred project name)

Install dependencies:

```bash
uv sync
```

### Run evaluations

Run deterministic evaluators on LangSmith:

```bash
uv run python evals/run_langsmith_eval.py --dataset evals/datasets/starter.jsonl
```

Include LLM-as-judge evaluators (slower/costly):

```bash
uv run python evals/run_langsmith_eval.py --dataset evals/datasets/starter.jsonl --with-llm-judge
```

Run locally only (no LangSmith upload), useful when you want quick checks in terminal:

```bash
uv run python evals/run_langsmith_eval.py --dataset evals/datasets/starter.jsonl --dry-run
```

### Where results appear

- **LangSmith run**: Prints an experiment URL and full results are visible in LangSmith.
- **Dry-run**: Prints per-example evaluator scores in your local terminal.

### What gets scored

- `route_correct` - expected branch routing (`post`/`email`/`qa`/`other`)
- `email_category_valid` - allowed email-category compliance when provided
- `post_platform_present` - platform extraction/compliance for post cases
- `qa_scope_handling` - in-scope vs out-of-scope QA behavior
- `response_quality_judge` - LLM-as-judge quality rubric (optional)
- `safety_overclaiming_judge` - LLM-as-judge safety/caution rubric (optional)

### Dataset format

`evals/datasets/starter.jsonl` uses one JSON object per line with:

- `inputs`: org context + `user_message`
- `outputs`: expected route and optional branch-specific references

## Architecture (Current Milestone)

The assistant uses a single LangGraph `StateGraph`:

1. **Organization profile** - scrape website and infer organization name.
2. **Conversational onboarding** - acknowledge context loading before open-ended chat begins.
3. **Router** - classify each message into `post`, `email`, `qa`, or `other`.
4. **Post branch** - LLM requirement analysis (platform/topic sufficiency), then research, pillar selection, draft, review, finalize.
5. **Email branch** - LLM requirement analysis (supported category/details sufficiency), then category validation, draft, review, finalize.
6. **Q&A branch** - LLM scope analysis, website + web retrieval, answer synthesis with source links.
7. **Other branch** - conversational out-of-scope/help response.

Key modules:

- `src/vee_assignment/graph/assistant.py` (unified graph + routing)
- `src/vee_assignment/graph/state.py` (shared `AssistantState`)
- `src/vee_assignment/graph/post_flow.py` (social post branch)
- `src/vee_assignment/graph/email_flow.py` (email branch)
- `src/vee_assignment/graph/qa_flow.py` (organization Q&A branch)
- `src/vee_assignment/prompts/router.py`, `prompts/post.py`, `prompts/email.py`, `prompts/qa.py`
- `src/vee_assignment/schemas/router.py`, `schemas/post.py`, `schemas/email.py`, `schemas/qa.py`
- `src/vee_assignment/config.py`, `tools/jina.py`, `cli.py`

## Notes For Next Milestones

The project is structured so organization Q&A can be added as a first-class graph branch without changing the current routing foundation.
