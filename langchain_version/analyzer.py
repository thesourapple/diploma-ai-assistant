# -*- coding: utf-8 -*-
"""
Этап 2: Кросс-анализ разделов.

Паттерн "Refine": модель НЕ читает весь диплом за раз.
  Шаг A: извлекаем структурированные тезисы из Введения (цели, задачи, гипотеза).
  Шаг B: извлекаем структурированные тезисы из Заключения (результаты, выводы).
  Шаг C: подаём модели ТОЛЬКО эти два коротких JSON (а не 60 страниц текста)
         и просим сверить их логически.

Это резко снижает риск галлюцинаций: модель сверяет 20 строк JSON, а не ищет
иголку в стоге сена по всему документу.
"""

from llm_client import ask_json


EXTRACT_INTRO_SYSTEM = """Ты — научный руководитель, который проверяет дипломные работы.
Твоя задача — извлечь из текста Введения строго структурированную информацию.
Отвечай ТОЛЬКО валидным JSON без пояснений, без markdown-обёртки.
Формат:
{
  "goal": "формулировка цели работы одним предложением, или null если цель не сформулирована явно",
  "objectives": ["задача 1", "задача 2", "..."],
  "hypothesis": "формулировка гипотезы, или null если гипотезы нет",
  "object_of_research": "объект исследования, или null",
  "subject_of_research": "предмет исследования, или null"
}
Если что-то не указано в тексте явно — используй null, не придумывай."""

EXTRACT_CONCLUSION_SYSTEM = """Ты — научный руководитель, который проверяет дипломные работы.
Извлеки из текста Заключения строго структурированную информацию.
Отвечай ТОЛЬКО валидным JSON без пояснений, без markdown-обёртки.
Формат:
{
  "results": ["результат/вывод 1", "результат/вывод 2", "..."],
  "hypothesis_verdict": "подтверждена / опровергнута / не упоминается / неясно",
  "explicit_claims_of_completion": ["фразы, где автор утверждает, что задача выполнена"]
}
Не придумывай факты, которых нет в тексте."""

CROSS_CHECK_SYSTEM = """Ты — строгий, но справедливый научный руководитель.
Тебе дают JSON с целями/задачами/гипотезой из Введения и JSON с результатами из Заключения
ОДНОЙ И ТОЙ ЖЕ дипломной работы. Твоя задача — логически сверить их.

Для КАЖДОЙ задачи из Введения определи, была ли она закрыта результатом в Заключении.
Также оцени, согласуется ли вердикт по гипотезе с тем, что вообще исследовалось.

Отвечай ТОЛЬКО валидным JSON:
{
  "goal_vs_results_match": "полное совпадение / частичное совпадение / несовпадение",
  "objectives_check": [
    {"objective": "текст задачи", "status": "выполнена/частично/не подтверждена в заключении", "comment": "краткое объяснение"}
  ],
  "hypothesis_check": {
    "status": "корректно подтверждена/опровергнута/недостаточно доказательств/гипотеза потеряна",
    "comment": "краткое объяснение"
  },
  "overall_logic_score": число от 0 до 10,
  "red_flags": ["конкретные логические нестыковки, если есть"]
}"""


def extract_intro_thesis(llm, intro_text: str) -> dict:
    return ask_json(llm, EXTRACT_INTRO_SYSTEM, intro_text)


def extract_conclusion_thesis(llm, conclusion_text: str) -> dict:
    return ask_json(llm, EXTRACT_CONCLUSION_SYSTEM, conclusion_text)


def cross_check(llm, intro_json: dict, conclusion_json: dict) -> dict:
    import json as _json
    user_prompt = (
        "ВВЕДЕНИЕ (извлечённые тезисы):\n"
        f"{_json.dumps(intro_json, ensure_ascii=False, indent=2)}\n\n"
        "ЗАКЛЮЧЕНИЕ (извлечённые тезисы):\n"
        f"{_json.dumps(conclusion_json, ensure_ascii=False, indent=2)}"
    )
    return ask_json(llm, CROSS_CHECK_SYSTEM, user_prompt)


def run_full_cross_analysis(llm, sections: dict) -> dict:
    """
    Полный пайплайн: Введение -> тезисы, Заключение -> тезисы, сверка.
    Возвращает всё вместе, чтобы можно было показать пользователю
    промежуточные результаты (прозрачность = меньше доверия "чёрному ящику").
    """
    intro_text = sections.get("Введение")
    conclusion_text = sections.get("Заключение")

    if not intro_text or not conclusion_text:
        return {
            "error": "Не найдены разделы 'Введение' и/или 'Заключение'. "
                     "Проверьте, что в документе используются стандартные заголовки Word (Heading 1)."
        }

    intro_thesis = extract_intro_thesis(llm, intro_text)
    conclusion_thesis = extract_conclusion_thesis(llm, conclusion_text)
    verdict = cross_check(llm, intro_thesis, conclusion_thesis)

    return {
        "intro_thesis": intro_thesis,
        "conclusion_thesis": conclusion_thesis,
        "verdict": verdict,
    }
