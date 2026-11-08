"""Extract appointment details with an open-source LLM served by Ollama."""
import json
import re
from datetime import date

import httpx

from . import config
from .prompts import SCHEMA, build_messages
from .validation import validate_fields


class LLMError(Exception):
    """The model could not be reached or did not return usable JSON."""


def _parse_json(content):
    try:
        return json.loads(content)
    except (TypeError, json.JSONDecodeError):
        match = re.search(r"\{.*\}", content or "", re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    raise LLMError("model did not return valid JSON")


def extract_llm(
    text,
    reference_date=None,
    *,
    client=None,
    url=None,
    model=None,
    prompt_version=None,
):
    """Return (fields, warnings). Raises LLMError on failure."""
    reference_date = reference_date or date.today()
    url = (url or config.OLLAMA_URL).rstrip("/")
    model = model or config.OLLAMA_MODEL
    prompt_version = prompt_version or config.PROMPT_VERSION

    payload = {
        "model": model,
        "messages": build_messages(text, reference_date, prompt_version),
        "format": SCHEMA,  # Ollama structured output: forces valid JSON in this shape
        "stream": False,
        "options": {"temperature": 0},
    }

    owns_client = client is None
    client = client or httpx.Client(timeout=config.OLLAMA_TIMEOUT)
    try:
        response = client.post(f"{url}/api/chat", json=payload)
        response.raise_for_status()
        content = response.json()["message"]["content"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise LLMError(f"could not get an answer from Ollama: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    return validate_fields(_parse_json(content))
