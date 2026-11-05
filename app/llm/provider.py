from abc import ABC, abstractmethod
import httpx
from openai import OpenAI
from app.core.config import settings


class LLMProviderError(RuntimeError):
    pass


class BaseLLMProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError


class OllamaProvider(BaseLLMProvider):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
        payload = {
            "model": settings.ollama_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": settings.llm_temperature},
        }
        try:
            response = httpx.post(url, json=payload, timeout=settings.llm_timeout_seconds)
            response.raise_for_status()
            data = response.json()
            answer = data.get("message", {}).get("content", "").strip()
            if not answer:
                raise LLMProviderError("Ollama returned an empty response.")
            return answer
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise LLMProviderError(f"Ollama request failed: {exc}") from exc


class OpenAIProvider(BaseLLMProvider):
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise LLMProviderError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")
        self.client = OpenAI(api_key=settings.openai_api_key, timeout=settings.llm_timeout_seconds)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=settings.openai_model,
                temperature=settings.llm_temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            answer = response.choices[0].message.content
            if not answer:
                raise LLMProviderError("OpenAI returned an empty response.")
            return answer.strip()
        except Exception as exc:
            if isinstance(exc, LLMProviderError):
                raise
            raise LLMProviderError(f"OpenAI request failed: {exc}") from exc


def get_llm_provider() -> BaseLLMProvider:
    provider = settings.llm_provider.strip().lower()
    if provider == "ollama":
        return OllamaProvider()
    if provider == "openai":
        return OpenAIProvider()
    raise LLMProviderError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
