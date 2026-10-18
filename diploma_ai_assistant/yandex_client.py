"""
Тонкий клиент для Yandex Cloud Foundation Models (YandexGPT).

Документация: https://yandex.cloud/ru/docs/foundation-models/concepts/yandexgpt/models
Эндпоинт completion: https://llm.api.cloud.yandex.net/foundationModels/v1/completion

Аутентификация — один из двух вариантов:
  * API-ключ сервисного аккаунта (заголовок Api-Key)  — YANDEX_API_KEY
  * IAM-токен (заголовок Bearer)                       — YANDEX_IAM_TOKEN
В обоих случаях также нужен идентификатор каталога:     YANDEX_FOLDER_ID

Переменные окружения читаются, если явно не передан параметр в конструктор.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Optional

import requests

_COMPLETION_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


class YandexGPTError(RuntimeError):
    pass


@dataclass
class YandexGPTResponse:
    text: str
    raw: dict


class YandexGPTClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        iam_token: Optional[str] = None,
        folder_id: Optional[str] = None,
        model: str = "yandexgpt",
        model_version: str = "latest",
        temperature: float = 0.2,
        max_tokens: int = 2000,
        timeout: int = 60,
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.environ.get("YANDEX_API_KEY")
        self.iam_token = iam_token or os.environ.get("YANDEX_IAM_TOKEN")
        self.folder_id = folder_id or os.environ.get("YANDEX_FOLDER_ID")
        self.model = model
        self.model_version = model_version
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries

        if not self.folder_id:
            raise ValueError(
                "Не задан YANDEX_FOLDER_ID (каталог Yandex Cloud). "
                "Передайте folder_id в конструктор или установите переменную окружения."
            )
        if not self.api_key and not self.iam_token:
            raise ValueError(
                "Нужен либо api_key (YANDEX_API_KEY), либо iam_token (YANDEX_IAM_TOKEN)."
            )

    @property
    def model_uri(self) -> str:
        return f"gpt://{self.folder_id}/{self.model}/{self.model_version}"

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json", "x-folder-id": self.folder_id}
        if self.api_key:
            headers["Authorization"] = f"Api-Key {self.api_key}"
        else:
            headers["Authorization"] = f"Bearer {self.iam_token}"
        return headers

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> YandexGPTResponse:
        """Один вызов completion. Возвращает текст ответа модели."""
        payload = {
            "modelUri": self.model_uri,
            "completionOptions": {
                "stream": False,
                "temperature": temperature if temperature is not None else self.temperature,
                "maxTokens": str(max_tokens if max_tokens is not None else self.max_tokens),
            },
            "messages": [
                {"role": "system", "text": system_prompt},
                {"role": "user", "text": user_prompt},
            ],
        }

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(
                    _COMPLETION_URL,
                    headers=self._headers(),
                    data=json.dumps(payload),
                    timeout=self.timeout,
                )
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise YandexGPTError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                resp.raise_for_status()
                data = resp.json()
                alternatives = data.get("result", {}).get("alternatives", [])
                if not alternatives:
                    raise YandexGPTError(f"Пустой ответ от API: {data}")
                text = alternatives[0]["message"]["text"]
                return YandexGPTResponse(text=text, raw=data)
            except (requests.RequestException, YandexGPTError, KeyError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 10))
                    continue
                raise YandexGPTError(f"Ошибка вызова YandexGPT после {attempt} попыток: {exc}") from exc

        raise YandexGPTError(f"Не удалось получить ответ: {last_error}")

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs,
    ) -> dict:
        """
        Вызов, ожидающий строго JSON в ответе. Если модель обернула JSON в
        ```json ... ``` — эти обёртки снимаются перед парсингом.
        """
        response = self.complete(system_prompt, user_prompt, **kwargs)
        cleaned = response.text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise YandexGPTError(
                f"Модель вернула невалидный JSON: {exc}\nОтвет модели:\n{response.text}"
            ) from exc


class YandexAIStudioClient:
    """
    Клиент для OpenAI-совместимого Responses API Yandex AI Studio.

    Поддерживает два режима вызова:

    1. ask_agent() — вызов уже сохранённого агента (созданного в Agent Atelier,
       вкладка "Новый агент" в интерфейсе AI Studio) по его prompt_id. Вся
       инструкция, температура, инструменты и т.д. уже настроены в самом
       агенте — сюда передаётся только текст сообщения пользователя.
       Это ровно тот вызов, что в вашем примере:

           client.responses.create(prompt={"id": prompt_id}, input="...")

    2. ask_model() — прямой вызов модели с явной инструкцией и текстом,
       без сохранённого агента (аналог chat.completions, но через Responses API).

    Обязательные переменные окружения (или параметры конструктора):
        YANDEX_API_KEY         — API-ключ сервисного аккаунта
        YANDEX_FOLDER_ID       — id каталога Yandex Cloud (используется как `project`)
    Опциональные:
        YANDEX_AGENT_PROMPT_ID — id сохранённого агента для ask_agent()
        YANDEX_MODEL            — modelUri для ask_model(), напр. gpt://<folder_id>/yandexgpt/latest
    """

    _DEFAULT_BASE_URL = "https://ai.api.cloud.yandex.net/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        folder_id: Optional[str] = None,
        prompt_id: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        try:
            from openai import OpenAI  # локальный импорт: openai — опциональная зависимость
        except ImportError as exc:
            raise ImportError(
                "Для YandexAIStudioClient нужен пакет openai: pip install openai"
            ) from exc

        self.api_key = api_key or os.environ.get("YANDEX_API_KEY")
        self.folder_id = folder_id or os.environ.get("YANDEX_FOLDER_ID")
        self.prompt_id = prompt_id or os.environ.get("YANDEX_AGENT_PROMPT_ID")
        self.model = model or os.environ.get("YANDEX_MODEL")

        if not self.api_key:
            raise ValueError("Не задан YANDEX_API_KEY.")
        if not self.folder_id:
            raise ValueError("Не задан YANDEX_FOLDER_ID (каталог Yandex Cloud, используется как project).")

        self._client = OpenAI(
            api_key=self.api_key,
            base_url=base_url or self._DEFAULT_BASE_URL,
            project=self.folder_id,
        )

    def ask_agent(self, input_text: str, previous_response_id: Optional[str] = None) -> tuple[str, str]:
        """
        Вызов сохранённого агента по prompt_id. Возвращает (текст_ответа, response_id).
        response_id можно передать в следующий вызов как previous_response_id, чтобы
        сохранить контекст диалога (истории/threads в Responses API нет — контекст
        передаётся именно так).
        """
        if not self.prompt_id:
            raise ValueError(
                "Не задан YANDEX_AGENT_PROMPT_ID — id агента, сохранённого в Agent Atelier "
                "(виден в интерфейсе AI Studio после создания агента)."
            )
        kwargs: dict = {"prompt": {"id": self.prompt_id}, "input": input_text}
        if previous_response_id:
            kwargs["previous_response_id"] = previous_response_id

        response = self._client.responses.create(**kwargs)
        return response.output_text, response.id

    def ask_model(
        self,
        instructions: str,
        input_text: str,
        temperature: float = 0.2,
        max_output_tokens: int = 1500,
    ) -> str:
        """Прямой вызов модели без сохранённого агента."""
        if not self.model:
            raise ValueError(
                "Не задана модель (YANDEX_MODEL), например: gpt://<folder_id>/yandexgpt/latest"
            )
        response = self._client.responses.create(
            model=self.model,
            instructions=instructions,
            input=input_text,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        return response.output_text
