"""Minimal LLM clients over plain HTTPS (stdlib only, no SDK to install).

Two providers behind one interface, `generate_json`:
  - Gemini  (GEMINI_API_KEY)  structured output enforced by a response schema
  - Groq    (GROQ_API_KEY)    OpenAI-compatible JSON mode; the schema goes in the prompt

The pipeline only ever sees the JSONModel protocol, so the provider is a config
choice, not a code change.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Protocol

GEMINI_DEFAULT_MODEL = "gemini-3.5-flash"
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"
_GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
_RETRYABLE = {429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    pass


class JSONModel(Protocol):
    """Anything that can turn a prompt into JSON. Tests use a fake."""

    model: str

    def generate_json(self, system: str, prompt: str, schema: dict[str, Any], temperature: float) -> dict[str, Any]: ...


class GeminiClient:
    def __init__(self, api_key: str, model: str = GEMINI_DEFAULT_MODEL, timeout: float = 150, retries: int = 5):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.retries = retries

    def generate_json(self, system: str, prompt: str, schema: dict[str, Any], temperature: float) -> dict[str, Any]:
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }
        data = _post_json(
            _GEMINI_ENDPOINT.format(model=self.model),
            {"x-goog-api-key": self.api_key},
            payload, self.timeout, self.retries, provider="Gemini",
        )
        candidates = data.get("candidates") or []
        if not candidates:
            reason = data.get("promptFeedback", {}).get("blockReason", "no candidates returned")
            raise LLMError(f"Gemini returned no output ({reason})")
        candidate = candidates[0]
        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if not text:
            raise LLMError(f"Gemini returned empty output (finishReason={candidate.get('finishReason')})")
        return _load_json(text, "Gemini")


class GroqClient:
    def __init__(self, api_key: str, model: str = GROQ_DEFAULT_MODEL, timeout: float = 90, retries: int = 5):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.retries = retries

    def generate_json(self, system: str, prompt: str, schema: dict[str, Any], temperature: float) -> dict[str, Any]:
        # JSON mode guarantees valid JSON but not the shape, so spell the shape out.
        shaped_prompt = (
            f"{prompt}\n\nRespond with a single JSON object matching this schema "
            f"(keys exactly as named):\n{json.dumps(schema, indent=2)}"
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": shaped_prompt}],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        data = _post_json(
            _GROQ_ENDPOINT, {"Authorization": f"Bearer {self.api_key}"},
            payload, self.timeout, self.retries, provider="Groq",
        )
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as err:
            raise LLMError(f"Groq returned an unexpected response: {str(data)[:200]}") from err
        return _load_json(text, "Groq")


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any],
               timeout: float, retries: int, provider: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "scriptbench/1.0", **headers},
        method="POST",
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", errors="replace")
            if err.code in _RETRYABLE and attempt < retries - 1:
                time.sleep(_retry_delay(detail, attempt, err.headers.get("retry-after")))
                continue
            raise LLMError(f"{provider} API returned HTTP {err.code}: {detail[:500]}") from err
        except (urllib.error.URLError, TimeoutError) as err:
            if attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            raise LLMError(f"Could not reach the {provider} API: {err}") from err
    raise LLMError("unreachable")  # loop always returns or raises


def _retry_delay(error_body: str, attempt: int, retry_after: str | None = None) -> float:
    """Use the server's hint when rate-limited, else exponential backoff."""
    if retry_after:
        try:
            return min(float(retry_after) + 1, 90)
        except ValueError:
            pass
    try:
        for detail in json.loads(error_body)["error"].get("details", []):
            if "retryDelay" in detail:
                return min(float(detail["retryDelay"].rstrip("s")) + 1, 90)
    except (ValueError, KeyError, TypeError, AttributeError):
        pass
    return min(5 * 2 ** attempt, 60)


def _load_json(text: str, provider: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError as err:
        raise LLMError(f"{provider} returned invalid JSON: {text[:200]}") from err


def load_dotenv(path: Path) -> None:
    """Read KEY=VALUE lines from a .env file without overriding real env vars."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def client_from_env() -> JSONModel | None:
    """Pick a provider: SCRIPTBENCH_PROVIDER if set, else whichever key is present (Gemini first)."""
    load_dotenv(Path.cwd() / ".env")
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    groq_key = os.environ.get("GROQ_API_KEY")
    provider = os.environ.get("SCRIPTBENCH_PROVIDER", "").lower() or ("gemini" if gemini_key else "groq" if groq_key else "")

    if provider == "gemini" and gemini_key:
        return GeminiClient(gemini_key, model=os.environ.get("GEMINI_MODEL", GEMINI_DEFAULT_MODEL))
    if provider == "groq" and groq_key:
        return GroqClient(groq_key, model=os.environ.get("GROQ_MODEL", GROQ_DEFAULT_MODEL))
    return None
