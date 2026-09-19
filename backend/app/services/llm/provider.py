"""LLM provider abstraction for LangChain.

Selects OpenAI or Anthropic based on `LLM_PROVIDER` and centralizes
configuration. Returns a `BaseChatModel` ready to invoke.
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import get_settings


logger = logging.getLogger(__name__)


def get_chat_model(
    *,
    purpose: str = "default",
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> BaseChatModel:
    settings = get_settings()
    provider = settings.llm_provider.lower()
    chosen_model = model or settings.llm_model
    chosen_temp = settings.llm_temperature if temperature is None else temperature
    chosen_max = settings.llm_max_tokens if max_tokens is None else max_tokens

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        if not settings.openai_api_key:
            logger.warning("OPENAI_API_KEY not set; LLM calls will fail at runtime")
        return ChatOpenAI(
            model=chosen_model,
            api_key=settings.openai_api_key or None,
            base_url=settings.openai_base_url or None,
            temperature=chosen_temp,
            max_tokens=chosen_max,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if not settings.anthropic_api_key:
            logger.warning("ANTHROPIC_API_KEY not set; LLM calls will fail at runtime")
        return ChatAnthropic(
            model=chosen_model,
            api_key=settings.anthropic_api_key or None,
            temperature=chosen_temp,
            max_tokens=chosen_max,
        )

    if provider == "minimax":
        from langchain_openai import ChatOpenAI

        if not settings.minimax_api_key:
            logger.warning("MINIMAX_API_KEY not set; LLM calls will fail at runtime")
        # MiniMax exposes an OpenAI-compatible API.
        return ChatOpenAI(
            model=chosen_model,
            api_key=settings.minimax_api_key or None,
            base_url=settings.minimax_base_url or None,
            temperature=chosen_temp,
            max_tokens=chosen_max,
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")