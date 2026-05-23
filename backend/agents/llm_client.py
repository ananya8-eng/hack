"""
Unified LLM client for agent orchestration.

Provider order: NVIDIA → Grok → HuggingFace → Gemini.
Each provider is skipped when unavailable or misconfigured.
"""
from __future__ import annotations

import json
import logging
from typing import Callable, Optional

STRICT_JSON_SUFFIX = (
    "\n\nCRITICAL: Respond with ONLY a valid JSON object. "
    "No markdown, no code fences, no prose before or after. "
    "The entire response must parse with json.loads()."
)

import requests

from backend.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.nvidia_api_key = settings.nvidia_api_key
        self.nvidia_base_url = settings.nvidia_api_base_url
        self.nvidia_model = settings.nvidia_model
        self.grok_api_key = settings.grok_api_key
        self.grok_base_url = settings.grok_api_base_url
        self.grok_model = settings.grok_model
        self.hf_api_key = settings.huggingface_api_key
        self.hf_model = settings.huggingface_model
        self.hf_inference_url = settings.huggingface_inference_url
        self.gemini_api_key = settings.gemini_api_key
        self.gemini_model = settings.gemini_model
        self.default_timeout = settings.llm_default_timeout

    def generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        timeout: int | None = None,
    ) -> str:
        effective_timeout = timeout if timeout is not None else self.default_timeout
        providers: list[tuple[str, Callable[[], str]]] = [
            ("nvidia", lambda: self._nvidia(prompt, temperature, effective_timeout)),
            ("grok", lambda: self._grok(prompt, temperature, effective_timeout)),
            (
                "huggingface",
                lambda: self._huggingface(prompt, temperature, effective_timeout),
            ),
            ("gemini", lambda: self._gemini(prompt, temperature, effective_timeout)),
        ]
        for name, fn in providers:
            try:
                text = fn()
                if text and text.strip():
                    logger.info("LLM response from provider: %s", name)
                    return text.strip()
            except Exception as exc:
                logger.debug("LLM provider %s unavailable: %s", name, exc)
        logger.warning("All LLM providers failed or returned empty")
        return ""

    def generate_json(
        self,
        prompt: str,
        *,
        temperature: float = 0.1,
        timeout: int | None = None,
        max_attempts: int = 3,
        validator: Callable[[dict], bool] | None = None,
    ) -> Optional[dict]:
        """
        Call the LLM and parse JSON, retrying when output is not valid JSON.
        Appends strict JSON formatting instructions on every attempt.
        """
        base_prompt = prompt.rstrip()
        if "json.loads()" not in base_prompt:
            base_prompt = f"{base_prompt}{STRICT_JSON_SUFFIX}"

        for attempt in range(1, max_attempts + 1):
            attempt_prompt = base_prompt
            if attempt > 1:
                attempt_prompt = (
                    f"{base_prompt}\n\n"
                    f"[Retry {attempt}/{max_attempts}] Your previous reply was not valid JSON. "
                    "Output ONLY a single JSON object. No markdown fences or extra text."
                )

            response_text = self.generate(
                attempt_prompt,
                temperature=temperature,
                timeout=timeout,
            )
            parsed = parse_json_from_llm(response_text) if response_text else None
            if parsed is not None and (validator is None or validator(parsed)):
                if attempt > 1:
                    logger.info("LLM returned parseable JSON on attempt %s", attempt)
                return parsed

            if attempt < max_attempts:
                logger.warning(
                    "LLM JSON parse failed (attempt %s/%s); retrying",
                    attempt,
                    max_attempts,
                )

        logger.warning("LLM did not return valid JSON after %s attempts", max_attempts)
        return None

    def _openai_compatible_chat(
        self,
        url: str,
        api_key: str,
        model: str,
        prompt: str,
        temperature: float,
        timeout: int,
    ) -> str:
        if not api_key:
            return ""
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            },
            timeout=timeout,
        )
        if response.status_code != 200:
            return ""
        payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        return message.get("content", "")

    def _nvidia(self, prompt: str, temperature: float, timeout: int) -> str:
        return self._openai_compatible_chat(
            self.nvidia_base_url,
            self.nvidia_api_key,
            self.nvidia_model,
            prompt,
            temperature,
            timeout,
        )

    def _grok(self, prompt: str, temperature: float, timeout: int) -> str:
        return self._openai_compatible_chat(
            self.grok_base_url,
            self.grok_api_key,
            self.grok_model,
            prompt,
            temperature,
            timeout,
        )

    def _huggingface(self, prompt: str, temperature: float, timeout: int) -> str:
        if not self.hf_api_key:
            return ""
        response = requests.post(
            self.hf_inference_url,
            headers={"Authorization": f"Bearer {self.hf_api_key}"},
            json={
                "inputs": prompt,
                "parameters": {"max_new_tokens": 2048, "temperature": temperature},
            },
            timeout=timeout,
        )
        if response.status_code != 200:
            return ""
        payload = response.json()
        if isinstance(payload, list) and payload:
            generated = payload[0].get("generated_text", "")
            if generated.startswith(prompt):
                return generated[len(prompt) :].strip()
            return generated
        if isinstance(payload, dict):
            return payload.get("generated_text", "")
        return ""

    def _gemini(self, prompt: str, temperature: float, timeout: int) -> str:
        if not self.gemini_api_key:
            return ""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini_model}:generateContent?key={self.gemini_api_key}"
        )
        response = requests.post(
            url,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature},
            },
            timeout=timeout,
        )
        if response.status_code != 200:
            return ""
        payload = response.json()
        candidates = payload.get("candidates") or []
        if not candidates:
            return ""
        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        if not parts:
            return ""
        return parts[0].get("text", "")


def _extract_json_object(text: str) -> Optional[str]:
    """Extract the first balanced JSON object from model output."""
    import re

    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_json_from_llm(text: str) -> Optional[dict]:
    if not text or not text.strip():
        return None

    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    candidate = _extract_json_object(stripped)
    if not candidate:
        logger.debug("LLM output contained no parseable JSON object")
        return None
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError as exc:
        logger.debug("LLM JSON parse failed: %s", exc)
        return None


llm_client = LLMClient()
