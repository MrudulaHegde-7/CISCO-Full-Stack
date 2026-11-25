from typing import Any

import httpx

from app.config import settings
from app.errors import ServiceUnavailableError


class GeminiClient:
    """Small REST adapter for Gemini generation and embedding APIs."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model = model or settings.gemini_model
        self.api_root = "https://generativelanguage.googleapis.com/v1beta"

    def _require_key(self) -> None:
        if not self.api_key:
            raise ServiceUnavailableError("Gemini is not configured. Set GEMINI_API_KEY in .env.")

    async def generate(
        self,
        contents: list[dict[str, Any]],
        *,
        system_instruction: str,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        self._require_key()
        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": 1200},
        }
        if tools:
            payload["tools"] = tools
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=5.0)) as client:
                response = await client.post(
                    f"{self.api_root}/models/{self.model}:generateContent",
                    headers={"x-goog-api-key": self.api_key},
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ServiceUnavailableError("Gemini is temporarily unavailable.") from exc

    async def embed(self, text: str, *, task_type: str) -> list[float]:
        self._require_key()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
                response = await client.post(
                    f"{self.api_root}/models/{settings.gemini_embedding_model}:embedContent",
                    headers={"x-goog-api-key": self.api_key},
                    json={
                        "model": f"models/{settings.gemini_embedding_model}",
                        "content": {"parts": [{"text": text}]},
                        "taskType": task_type,
                    },
                )
                response.raise_for_status()
                return response.json()["embedding"]["values"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise ServiceUnavailableError("Gemini embeddings are temporarily unavailable.") from exc