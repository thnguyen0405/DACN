"""LLM API abstraction and strict edge-weight response validation."""

from __future__ import annotations

import json
import http.client
import os
import urllib.error
import urllib.request
import warnings
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


NEUTRAL_MISSING_WEIGHT = 0.5
DEFAULT_OPENROUTER_MODEL = "openrouter/free"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_TEMPERATURE = 0.0


class LLMProviderError(RuntimeError):
    """Raised when an LLM request or response cannot be used."""


class DuplicateEdgeWeightWarning(UserWarning):
    """Emitted when an identical repeated LLM edge-weight record is ignored."""


class _RetryableOpenRouterError(Exception):
    """Internal signal carrying the final user-facing transport error."""

    def __init__(self, error: LLMProviderError, retry_message: str) -> None:
        super().__init__(str(error))
        self.error = error
        self.retry_message = retry_message


class LLMWeightProvider(ABC):
    """Replaceable interface for general or future adapted LLMs."""

    @abstractmethod
    def get_edge_weights(
        self, graph: dict[str, Any], start_region: str, goal_region: str
    ) -> dict[str, Any]:
        """Return the provider's decoded JSON response."""


def load_dotenv(path: Path = Path(".env")) -> None:
    """Load a small .env file without overriding existing environment values."""

    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip().strip("\"").strip("'")
        if name:
            os.environ.setdefault(name, value)


def graph_prompt_data(
    graph: dict[str, Any], start_region: str, goal_region: str
) -> dict[str, Any]:
    """Build the compact, topology-constrained data sent to the model."""

    return {
        "start_region": start_region,
        "goal_region": goal_region,
        "regions": [
            {"id": vertex["id"], "centroid": vertex["centroid"]}
            for vertex in graph["vertices"]
        ],
        "edges": [
            {
                "source": edge["source"],
                "target": edge["target"],
                "relation": edge["relation"],
            }
            for edge in graph["directed_edges"]
        ],
    }


class OpenRouterWeightProvider(LLMWeightProvider):
    """OpenRouter Chat Completions provider using only configured models.

    The rest of the planner depends only on ``LLMWeightProvider``, so a future
    API or fine-tuned-model adapter does not affect graph search.  This class
    never changes models automatically, which prevents an accidental paid
    fallback.
    """

    def __init__(
        self,
        prompt_path: Path,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float | None = None,
        timeout: float = 60.0,
        debug_response_path: Path = Path("outputs/openrouter_invalid_response.txt"),
    ) -> None:
        self.prompt_path = prompt_path
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.model = (
            model
            or os.environ.get("OPENROUTER_MODEL")
            or DEFAULT_OPENROUTER_MODEL
        )
        self.base_url = (
            base_url
            or os.environ.get("OPENROUTER_BASE_URL")
            or DEFAULT_OPENROUTER_BASE_URL
        ).rstrip("/")
        configured_temperature: float | str = (
            temperature
            if temperature is not None
            else os.environ.get(
                "OPENROUTER_TEMPERATURE", str(DEFAULT_OPENROUTER_TEMPERATURE)
            )
        )
        try:
            self.temperature = float(configured_temperature)
        except (TypeError, ValueError) as exc:
            raise LLMProviderError(
                "OPENROUTER_TEMPERATURE must be a numeric value between 0 and 2."
            ) from exc
        if not 0.0 <= self.temperature <= 2.0:
            raise LLMProviderError(
                "OPENROUTER_TEMPERATURE must be between 0 and 2."
            )
        self.timeout = timeout
        self.debug_response_path = debug_response_path
        if not self.api_key:
            raise LLMProviderError(
                "OPENROUTER_API_KEY is not set. Create a key at "
                "https://openrouter.ai/keys and add it to the environment or .env file."
            )

    def get_edge_weights(
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
            "edge_weights": result.get("edge_weights"),
        }

    def _get_model_json(self, prompt: str) -> tuple[dict[str, Any], str | None]:
        """Send one JSON-object prompt using the existing safe transport policy."""

        request_body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "stream": False,
            "temperature": self.temperature,
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        for attempt in range(2):
            try:
                payload = self._request_http_json(request)
                break
            except _RetryableOpenRouterError as exc:
                if attempt == 0:
                    print(exc.retry_message)
                    continue
                raise exc.error from exc

        try:
            model_text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(
                "OpenRouter response did not contain choices[0].message.content"
            ) from exc
        if not isinstance(model_text, str):
            raise LLMProviderError("OpenRouter model content must be a JSON string")
        try:
            result = json.loads(model_text)
        except json.JSONDecodeError as exc:
            raise LLMProviderError(f"LLM model content returned invalid JSON: {exc}") from exc
        if not isinstance(result, dict):
            raise LLMProviderError("LLM model content must decode to a JSON object")
        resolved_model = payload.get("model")
        if not isinstance(resolved_model, str):
            resolved_model = None
        return result, resolved_model

    def _request_http_json(self, request: urllib.request.Request) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = getattr(response, "status", None)
                if status is None:
                    status = response.getcode()
                headers = getattr(response, "headers", None)
                content_type = (
                    headers.get("Content-Type") if headers else None
                ) or "unknown"
                try:
                    raw_body = response.read()
                except http.client.IncompleteRead as exc:
                    raw_body = exc.partial
                    error = self._invalid_http_json_error(
                        status, content_type, raw_body, exc
                    )
                    raise _RetryableOpenRouterError(
                        error,
                        "Retrying OpenRouter request once because the response was malformed...",
                    ) from exc
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            error = self._http_error(exc.code, detail)
            if 500 <= exc.code <= 599:
                raise _RetryableOpenRouterError(
                    error,
                    f"Retrying OpenRouter request once after transient HTTP {exc.code}...",
                ) from exc
            raise error from exc
        except _RetryableOpenRouterError:
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionResetError) as exc:
            safe_error = self._redact_text(str(exc))
            error = LLMProviderError(f"OpenRouter network error: {safe_error}")
            raise _RetryableOpenRouterError(
                error,
                "Retrying OpenRouter request once after a transient network error...",
            ) from exc

        media_type = content_type.lower().split(";", 1)[0].strip()
        if media_type == "text/event-stream" or raw_body.lstrip().startswith(b"data:"):
            saved_path = self._save_debug_response(raw_body)
            raise LLMProviderError(
                "OpenRouter returned an unexpected streaming/SSE response even though "
                "stream=false was requested.\n"
                f"HTTP status: {status}\n"
                f"Content-Type: {content_type}\n"
                f"Response bytes: {len(raw_body)}\n"
                f"Raw response saved to {saved_path}"
            )

        try:
            decoded_body = raw_body.decode("utf-8")
            payload = json.loads(decoded_body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            error = self._invalid_http_json_error(status, content_type, raw_body, exc)
            raise _RetryableOpenRouterError(
                error,
                "Retrying OpenRouter request once because the response was malformed...",
            ) from exc
        if not isinstance(payload, dict):
            error = self._invalid_http_json_error(
                status,
                content_type,
                raw_body,
                ValueError("top-level HTTP JSON must be an object"),
            )
            raise _RetryableOpenRouterError(
                error,
                "Retrying OpenRouter request once because the response was malformed...",
            )
        return payload

    def _invalid_http_json_error(
        self,
        status: int | str,
        content_type: str,
        raw_body: bytes,
        parse_error: Exception,
    ) -> LLMProviderError:
        saved_path = self._save_debug_response(raw_body)
        return LLMProviderError(
            "OpenRouter returned invalid HTTP JSON.\n"
            f"HTTP status: {status}\n"
            f"Content-Type: {content_type}\n"
            f"Response bytes: {len(raw_body)}\n"
            f"JSON parsing error: {self._redact_text(str(parse_error))}\n"
            f"Raw response saved to {saved_path}"
        )

    def _save_debug_response(self, raw_body: bytes) -> str:
        path = self.debug_response_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self._redact_bytes(raw_body))
            return str(path)
        except OSError as exc:
            return f"{path} (save failed: {self._redact_text(str(exc))})"

    def _redact_text(self, value: str) -> str:
        return value.replace(self.api_key, "[REDACTED]") if self.api_key else value

    def _redact_bytes(self, value: bytes) -> bytes:
        if not self.api_key:
            return value
        return value.replace(self.api_key.encode("utf-8"), b"[REDACTED]")

    def _http_error(self, status: int, detail: str) -> LLMProviderError:
        compact_detail = self._redact_text(" ".join(detail.split()))
        suffix = f" Details: {compact_detail}" if compact_detail else ""
        if status in (401, 403):
            return LLMProviderError(
                f"OpenRouter authentication failed (HTTP {status}). Check OPENROUTER_API_KEY.{suffix}"
            )
        if status == 429:
            return LLMProviderError(
                "OpenRouter free-model rate limit reached (HTTP 429). Wait for the limit "
                f"to reset; free services have restricted quotas.{suffix}"
            )
        lowered_detail = compact_detail.lower()
        if status in (400, 422) and "response_format" in lowered_detail and any(
            word in lowered_detail for word in ("unsupported", "not support", "invalid")
        ):
            return LLMProviderError(
                f"OpenRouter model '{self.model}' does not support "
                "response_format={\"type\":\"json_object\"}. Choose a model that "
                f"supports JSON output; no fallback model was attempted.{suffix}"
            )
        unavailable_words = ("model", "unavailable", "no endpoints", "not found", "provider")
        if status in (404, 502, 503) or (
            status == 400 and any(word in compact_detail.lower() for word in unavailable_words)
        ):
            if self.model == "openrouter/free":
                guidance = (
                    "Try again later or manually select another model whose ID ends in "
                    "':free'."
                )
            else:
                guidance = "To manually use the free-model router, set OPENROUTER_MODEL=openrouter/free."
            return LLMProviderError(
                f"OpenRouter model '{self.model}' is unavailable (HTTP {status}). "
                f"{guidance} No paid fallback was attempted.{suffix}"
            )
        return LLMProviderError(f"OpenRouter API returned HTTP {status}.{suffix}")


def parse_weight_response(response: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except json.JSONDecodeError as exc:
            raise LLMProviderError(f"LLM returned invalid JSON: {exc}") from exc
    if not isinstance(response, dict):
        raise LLMProviderError("LLM response must be a JSON object")
    if not isinstance(response.get("edge_weights"), list):
        raise LLMProviderError("LLM response field 'edge_weights' must be a list")
    return response


def validate_edge_weights(
    response: str | dict[str, Any],
    graph: dict[str, Any],
    missing_weight: float = NEUTRAL_MISSING_WEIGHT,
) -> tuple[dict[tuple[str, str], float], list[tuple[str, str]]]:
    """Validate topology and range; default only individually missing edges."""

    parsed = parse_weight_response(response)
    region_ids = {vertex["id"] for vertex in graph["vertices"]}
    valid_edges = {
        (edge["source"], edge["target"]) for edge in graph["directed_edges"]
    }
    weights: dict[tuple[str, str], float] = {}

    for index, item in enumerate(parsed["edge_weights"]):
        if not isinstance(item, dict):
            raise LLMProviderError(f"edge_weights[{index}] must be an object")
        source, target, weight = item.get("source"), item.get("target"), item.get("weight")
        if not isinstance(source, str) or not isinstance(target, str):
            raise LLMProviderError(f"edge_weights[{index}] needs string source and target")
        if source not in region_ids or target not in region_ids:
            raise LLMProviderError(f"Weight references unknown region: {source}->{target}")
        key = (source, target)
        if key not in valid_edges:
            raise LLMProviderError(f"Weight references nonexistent edge: {source}->{target}")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise LLMProviderError(f"Weight for {source}->{target} must be numeric")
        numeric_weight = float(weight)
        if not 0.0 < numeric_weight <= 1.0:
            raise LLMProviderError(
                f"Weight for {source}->{target}: Weight must be greater than 0 "
                "and less than or equal to 1."
            )
        if key in weights:
            if weights[key] == numeric_weight:
                warnings.warn(
                    f"Ignored identical duplicate LLM edge-weight record for {source}->{target}.",
                    DuplicateEdgeWeightWarning,
                    stacklevel=2,
                )
                continue
            raise LLMProviderError(
                f"Conflicting duplicate weights for {source}->{target}: "
                f"{weights[key]} and {numeric_weight}"
            )
        weights[key] = numeric_weight

    if valid_edges and not weights:
        raise LLMProviderError("LLM response contains no usable edge weights")
    missing = sorted(valid_edges - weights.keys())
    for key in missing:
        weights[key] = missing_weight
    return weights, missing
