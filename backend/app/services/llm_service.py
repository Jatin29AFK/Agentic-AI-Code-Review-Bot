from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMConfigurationError(RuntimeError):
    """Raised when the LLM provider is not configured correctly."""


class LLMResponseError(RuntimeError):
    """Raised when the LLM returns unusable output."""


class LLMService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_structured(
        self,
        *,
        task_name: str,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
    ) -> BaseModel:
        self._ensure_configured()
        schema = json.dumps(response_model.model_json_schema(), indent=2)
        messages = [
            {
                "role": "system",
                "content": (
                    f"{system_prompt}\n"
                    "Return valid JSON only. Do not wrap it in markdown.\n"
                    f"Follow this JSON schema:\n{schema}"
                ),
            },
            {"role": "user", "content": user_prompt},
        ]

        content = self._chat_completion(messages)
        parsed = self._parse_json(content)
        try:
            return response_model.model_validate(parsed)
        except ValidationError as exc:
            logger.warning("Initial structured validation failed for %s: %s", task_name, exc)
            repaired = self._repair_json(task_name=task_name, schema=schema, invalid_payload=content)
            try:
                return response_model.model_validate(repaired)
            except ValidationError as repair_exc:
                raise LLMResponseError(
                    f"LLM response for {task_name} could not be validated after repair: {repair_exc}"
                ) from repair_exc

    def _ensure_configured(self) -> None:
        if not self.settings.llm_api_key:
            raise LLMConfigurationError("LLM_API_KEY is missing. Add it to your environment before running reviews.")

    def _chat_completion(self, messages: list[dict[str, str]]) -> str:
        provider = self.settings.llm_provider.lower()
        if provider not in {"openai", "openai_compatible", "groq", "openrouter"}:
            raise LLMConfigurationError(
                f"Unsupported LLM_PROVIDER '{self.settings.llm_provider}'. Use openai, groq, openrouter, or openai_compatible."
            )

        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": 0.1,
        }

        if provider == "openrouter":
            headers["HTTP-Referer"] = "https://localhost"
            headers["X-Title"] = "Agentic AI Code Review Bot"

        url = f"{self.settings.resolved_llm_base_url}/chat/completions"
        try:
            with httpx.Client(timeout=self.settings.llm_timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500]
            raise LLMResponseError(f"LLM provider request failed ({exc.response.status_code}): {body}") from exc
        except httpx.HTTPError as exc:
            raise LLMResponseError(f"Unable to reach LLM provider: {exc}") from exc

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError("LLM provider returned an unexpected response shape.") from exc

    def _repair_json(self, *, task_name: str, schema: str, invalid_payload: str) -> dict:
        repair_messages = [
            {
                "role": "system",
                "content": (
                    f"You fix malformed JSON for the task {task_name}. "
                    "Return valid JSON only, matching the provided schema."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Schema:\n{schema}\n\n"
                    f"Malformed output:\n{invalid_payload}"
                ),
            },
        ]
        repaired = self._chat_completion(repair_messages)
        return self._parse_json(repaired)

    def _parse_json(self, content: str) -> dict:
        stripped = content.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        fenced_match = re.search(r"```json\s*(\{.*\}|\[.*\])\s*```", stripped, re.DOTALL)
        if fenced_match:
            return json.loads(fenced_match.group(1))

        object_match = re.search(r"(\{.*\}|\[.*\])", stripped, re.DOTALL)
        if object_match:
            return json.loads(object_match.group(1))

        raise LLMResponseError("LLM response did not contain valid JSON.")
