from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langsmith import Client
from langsmith.utils import LangSmithAuthError

try:
    from evals.evaluators import (
        email_category_valid,
        post_platform_present,
        qa_scope_handling,
        response_quality_judge,
        route_correct,
        safety_overclaiming_judge,
    )
    from evals.targets import AssistantEvalTarget
except ModuleNotFoundError:  # pragma: no cover - script execution fallback
    from evaluators import (  # type: ignore[no-redef]
        email_category_valid,
        post_platform_present,
        qa_scope_handling,
        response_quality_judge,
        route_correct,
        safety_overclaiming_judge,
    )
    from targets import AssistantEvalTarget  # type: ignore[no-redef]
from vee_assignment.config import Settings


def _load_jsonl_dataset(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    examples: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if "inputs" not in row or "outputs" not in row:
            raise ValueError("Each dataset row must contain `inputs` and `outputs` keys.")
        examples.append({"inputs": row["inputs"], "outputs": row["outputs"]})
    return examples


def _create_langsmith_dataset(client: Client, dataset_name: str, examples: list[dict[str, Any]]) -> str:
    dataset = client.create_dataset(dataset_name=dataset_name)
    client.create_examples(dataset_id=dataset.id, examples=examples)
    return dataset.name


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LangSmith evaluation for assistant outputs.")
    parser.add_argument(
        "--dataset",
        default="evals/datasets/starter.jsonl",
        help="Path to local JSONL examples with `inputs` and `outputs`.",
    )
    parser.add_argument(
        "--experiment-prefix",
        default="vee-assignment-eval",
        help="LangSmith experiment name prefix.",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=4,
        help="Parallel worker count for evaluation runs.",
    )
    parser.add_argument(
        "--with-llm-judge",
        action="store_true",
        help="Include LLM-as-judge evaluators (slower and higher cost).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run target and evaluators locally without uploading to LangSmith.",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    examples = _load_jsonl_dataset(dataset_path)
    if not examples:
        raise ValueError(f"No examples loaded from {dataset_path}")

    settings = Settings.from_env()
    target = AssistantEvalTarget(settings=settings)

    evaluators: list[Any] = [route_correct, email_category_valid, post_platform_present, qa_scope_handling]
    if args.with_llm_judge:
        evaluators.extend([response_quality_judge, safety_overclaiming_judge])

    if args.dry_run:
        _run_dry_run(examples, target, evaluators)
        return

    client = Client()
    experiment_prefix = f"{args.experiment_prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    try:
        dataset_name = f"{experiment_prefix}-dataset"
        dataset_ref = _create_langsmith_dataset(client, dataset_name=dataset_name, examples=examples)

        results = client.evaluate(
            target,
            data=dataset_ref,
            evaluators=evaluators,
            experiment_prefix=experiment_prefix,
            description=f"Dataset: {dataset_name} from {dataset_path.name} | rows={len(examples)} | llm_judge={args.with_llm_judge}",
            max_concurrency=args.max_concurrency,
        )
    except LangSmithAuthError as exc:
        print("LangSmith authentication failed. Check LANGSMITH_API_KEY and LANGSMITH endpoint settings.")
        print(str(exc))
        print("Tip: run with --dry-run to validate the harness locally without LangSmith upload.")
        raise SystemExit(2) from exc

    print(f"Started evaluation: {experiment_prefix}")
    print(f"LangSmith dataset: {dataset_ref}")
    url = getattr(results, "url", None) or getattr(results, "_url", None)
    if url:
        print(f"LangSmith experiment: {url}")


def _run_dry_run(examples: list[dict[str, Any]], target: Any, evaluators: list[Any]) -> None:
    print(f"Dry run over {len(examples)} examples")
    for idx, example in enumerate(examples[:5], start=1):
        inputs = example["inputs"]
        reference_outputs = example["outputs"]
        outputs = target(inputs)
        print(f"\nExample {idx}")
        print(f"inputs.user_message: {inputs.get('user_message', '')}")
        print(f"route: {outputs.get('route', '')}")
        for evaluator in evaluators:
            name = getattr(evaluator, "__name__", "evaluator")
            score = evaluator(inputs, outputs, reference_outputs)
            print(f"- {name}: {score}")


if __name__ == "__main__":
    main()

