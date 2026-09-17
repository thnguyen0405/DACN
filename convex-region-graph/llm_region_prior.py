#!/usr/bin/env python3
"""Ask an LLM for per-region importance scores for sampling-based planning."""

from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from graph_utils import load_json_object, prepare_planning_graph, require_region
from llm_weight_provider import (
    LLMProviderError,
    OpenRouterWeightProvider,
    graph_prompt_data,
    load_dotenv,
)


MISSING_REGION_SCORE = 0.1


class MissingRegionScoreWarning(UserWarning):
    """Emitted when omitted graph regions receive the documented prior floor."""


class LLMRegionPriorProvider(ABC):
    """Replaceable interface for general or future adapted region-prior models."""

    @abstractmethod
    def get_region_scores(
        self, graph: dict[str, Any], start_region: str, goal_region: str
    ) -> dict[str, Any]:
        """Return the provider's decoded region-score response."""


class OpenRouterRegionPriorProvider(OpenRouterWeightProvider, LLMRegionPriorProvider):
    """Region-prior task using the existing safe OpenRouter transport."""

    def get_region_scores(
        self, graph: dict[str, Any], start_region: str, goal_region: str
    ) -> dict[str, Any]:
        template = self.prompt_path.read_text(encoding="utf-8")
        prompt = template.rstrip() + "\n\nINPUT GRAPH DATA:\n" + json.dumps(
            graph_prompt_data(graph, start_region, goal_region), ensure_ascii=False
        )
        result, resolved_model = self._get_model_json(prompt)
        return {
            "provider_metadata": {
                "provider": "openrouter",
                "requested_model": self.model,
                "resolved_model": resolved_model,
                "temperature": self.temperature,
            },
            "region_scores": result.get("region_scores"),
        }


def parse_region_score_response(response: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except json.JSONDecodeError as exc:
            raise LLMProviderError(f"LLM returned invalid JSON: {exc}") from exc
    if not isinstance(response, dict):
        raise LLMProviderError("LLM region-prior response must be a JSON object")
    if not isinstance(response.get("region_scores"), list):
        raise LLMProviderError("LLM response field 'region_scores' must be a list")
    return response


def validate_region_scores(
    response: str | dict[str, Any],
    graph: dict[str, Any],
    missing_score: float = MISSING_REGION_SCORE,
) -> tuple[dict[str, float], list[str]]:
    """Validate region IDs and scores, then fill individually omitted regions."""

    if not math.isfinite(missing_score) or not 0.0 < missing_score <= 1.0:
        raise ValueError("Missing-region fallback score must be in (0, 1]")
    parsed = parse_region_score_response(response)
    region_order = [vertex["id"] for vertex in graph["vertices"]]
    known = set(region_order)
    scores: dict[str, float] = {}

    for index, item in enumerate(parsed["region_scores"]):
        if not isinstance(item, dict):
            raise LLMProviderError(f"region_scores[{index}] must be an object")
        region_id, score = item.get("id"), item.get("score")
        if not isinstance(region_id, str):
            raise LLMProviderError(f"region_scores[{index}] needs a string id")
        if region_id not in known:
            raise LLMProviderError(f"Region score references unknown region: {region_id}")
        if region_id in scores:
            raise LLMProviderError(f"Duplicate region score for {region_id}")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise LLMProviderError(f"Score for {region_id} must be numeric")
        numeric_score = float(score)
        if not math.isfinite(numeric_score) or not 0.0 < numeric_score <= 1.0:
            raise LLMProviderError(
                f"Score for {region_id} must be greater than 0 and less than or equal to 1"
            )
        scores[region_id] = numeric_score

    if known and not scores:
        raise LLMProviderError("LLM response contains no usable region scores")
    missing = [region_id for region_id in region_order if region_id not in scores]
    if missing:
        warnings.warn(
            f"Assigned fallback score {missing_score} to {len(missing)} omitted region(s).",
            MissingRegionScoreWarning,
            stacklevel=2,
        )
        for region_id in missing:
            scores[region_id] = missing_score
    return scores, missing


def build_region_prior(
    raw_graph: dict[str, Any],
    start_region: str,
    goal_region: str,
    response: dict[str, Any] | None = None,
    provider: LLMRegionPriorProvider | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, float], list[str]]:
    graph = prepare_planning_graph(raw_graph)
    require_region(graph, start_region, "start")
    require_region(graph, goal_region, "goal")
    if response is None:
        if provider is None:
            raise LLMProviderError("A region-score response or provider is required")
        response = provider.get_region_scores(graph, start_region, goal_region)

    scores, missing = validate_region_scores(response, graph)
    parsed = parse_region_score_response(response)
    reasons = {
        item["id"]: item.get("reason")
        for item in parsed["region_scores"]
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and isinstance(item.get("reason"), str)
    }
    records = []
    for vertex in graph["vertices"]:
        region_id = vertex["id"]
        record: dict[str, Any] = {"id": region_id, "score": scores[region_id]}
        if region_id in reasons:
            record["reason"] = reasons[region_id]
        elif region_id in missing:
            record["reason"] = "Fallback score for a region omitted by the LLM."
        records.append(record)

    metadata = response.get("provider_metadata")
    prior: dict[str, Any] = {
        "start_region": start_region,
        "goal_region": goal_region,
        "region_scores": records,
    }
    if isinstance(metadata, dict):
        prior = {"provider_metadata": dict(metadata), **prior}
    return prior, graph, scores, missing


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path, help="GCR JSON file")
    parser.add_argument("--start", required=True, help="Start region ID")
    parser.add_argument("--goal", required=True, help="Goal region ID")
    parser.add_argument("--provider", choices=["openrouter"], default="openrouter")
    parser.add_argument("--response", type=Path, help="Reuse saved region-score JSON; skips the API")
    parser.add_argument("--output", type=Path, default=Path("outputs/region_prior.json"))
    parser.add_argument(
        "--prompt",
        type=Path,
        default=Path(__file__).parent / "prompts" / "region_prior_prompt.txt",
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        raw_graph = load_json_object(args.graph)
        graph = prepare_planning_graph(raw_graph)
        require_region(graph, args.start, "start")
        require_region(graph, args.goal, "goal")
        if args.response:
            print(f"Reusing region scores from {args.response}; API call skipped.")
            response = load_json_object(args.response)
            provider = None
        else:
            load_dotenv(args.env_file)
            print("Calling OpenRouter for region importance scores...")
            provider = OpenRouterRegionPriorProvider(args.prompt)
            response = provider.get_region_scores(graph, args.start, args.goal)
            metadata = response.get("provider_metadata", {})
            print(f"Requested model: {metadata.get('requested_model') or provider.model}")
            if metadata.get("resolved_model"):
                print(f"Resolved model: {metadata['resolved_model']}")

        prior, _, _, missing = build_region_prior(
            raw_graph, args.start, args.goal, response=response, provider=provider
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(prior, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"Saved region prior for {len(prior['region_scores'])} regions to {args.output}")
        if missing:
            print(f"Fallback score {MISSING_REGION_SCORE} was used for: {', '.join(missing)}")
        return 0
    except (OSError, ValueError, LLMProviderError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
