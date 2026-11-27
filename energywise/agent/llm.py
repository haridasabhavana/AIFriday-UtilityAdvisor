"""LiteLLM gateway client with fallback model and USD budget cap (D-10)."""

import logging
from typing import Any, Dict, List, Optional

import httpx
from openai import OpenAI

from energywise.config import CHAT_MODEL, FALLBACK_MODEL, LITELLM_API_KEY, LITELLM_BASE_URL, LLM_BUDGET_USD

logger = logging.getLogger("energywise.llm")

_SPEND_USD = 0.0


def call_llm(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    timeout: float = 12.0,
) -> Any:
    """Invoke LiteLLM gateway with primary CHAT_MODEL and fallback FALLBACK_MODEL."""
    global _SPEND_USD
    if not LITELLM_API_KEY:
        raise RuntimeError("LITELLM_API_KEY not configured")
    if _SPEND_USD >= LLM_BUDGET_USD:
        raise RuntimeError(f"App LLM budget cap (${LLM_BUDGET_USD:.2f}) reached")

    base = LITELLM_BASE_URL.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"

    http_client = httpx.Client(verify=False, timeout=timeout)
    client = OpenAI(base_url=base, api_key=LITELLM_API_KEY, http_client=http_client)

    last_err: Exception | None = None
    for model in (CHAT_MODEL, FALLBACK_MODEL):
        try:
            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 400,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            resp = client.chat.completions.create(**kwargs)
            _SPEND_USD += 0.002  # conservative PoC spend accounting per call
            return resp
        except Exception as exc:
            logger.warning("Gateway call failed on %s: %s", model, exc)
            last_err = exc
    raise RuntimeError(f"All gateway models failed: {last_err}")
