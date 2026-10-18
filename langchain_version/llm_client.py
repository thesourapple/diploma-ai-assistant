# -*- coding: utf-8 -*-
"""
Тонкая обёртка над LangChain, чтобы остальной код не зависел от конкретного
провайдера модели. Поддерживает Anthropic (Claude) "из коробки".
Ключ API берётся из переменной окружения ANTHROPIC_API_KEY.
"""

import os
import json
import re
from config import DEFAULT_MODEL, DEFAULT_TEMPERATURE


def get_llm(model_name: str = DEFAULT_MODEL, temperature: float = DEFAULT_TEMPERATURE):
    """
    Возвращает LangChain chat-модель.
    Требует: pip install langchain-anthropic anthropic
    """
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as e:
        raise RuntimeError(
            "Не установлен пакет langchain-anthropic.\n"
            "Установите: pip install langchain-anthropic anthropic"
        ) from e

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Не найден ANTHROPIC_API_KEY в переменных окружения.\n"
            "Задайте его командой: export ANTHROPIC_API_KEY=sk-ant-..."
        )

    return ChatAnthropic(model=model_name, temperature=temperature, api_key=api_key)


def ask_json(llm, system_prompt: str, user_prompt: str) -> dict:
    """
    Отправляет запрос модели и парсит JSON-ответ.
    Устойчиво к тому, что модель иногда оборачивает JSON в ```json ... ```.
    """
    from langchain_core.messages import SystemMessage, HumanMessage

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    response = llm.invoke(messages)
    raw = response.content if isinstance(response.content, str) else str(response.content)

    # Убираем возможные markdown-обёртки ```json ... ```
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Пытаемся вытащить первый JSON-объект из текста регуляркой как fallback
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"Модель вернула не-JSON ответ:\n{raw}")
