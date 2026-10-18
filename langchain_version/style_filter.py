# -*- coding: utf-8 -*-
"""
Этап 3: Стилистический фильтр.

Работает в два слоя:
  1. Быстрый детерминированный regex-слой (аналог метрики "Главреда") —
     считает долю "словесного мусора" без единого вызова LLM. Это KPI из задания.
  2. Опциональный LLM-слой — берёт самые "грязные" предложения и переписывает
     их в строгом академическом стиле, показывая было/стало.
"""

import re
from config import COMPILED_CLICHES


def split_sentences(text: str) -> list:
    """Простое разбиение на предложения (без внешних NLP-библиотек)."""
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def analyze_water_level(text: str) -> dict:
    """
    Детерминированный анализ "воды" по всему разделу/документу.
    Возвращает метрики + список конкретных найденных клише с категориями.
    """
    sentences = split_sentences(text)
    total_words = max(len(text.split()), 1)

    findings = []  # [{category, pattern_match, sentence}, ...]
    category_counts = {cat: 0 for cat in COMPILED_CLICHES}

    for sentence in sentences:
        for category, patterns in COMPILED_CLICHES.items():
            for pattern in patterns:
                if pattern.search(sentence):
                    category_counts[category] += 1
                    findings.append({
                        "category": category,
                        "sentence": sentence,
                    })
                    break  # одно совпадение по категории на предложение достаточно

    total_hits = sum(category_counts.values())
    # "Индекс воды" — доля предложений с найденным штампом от всех предложений
    water_index = round(100 * total_hits / max(len(sentences), 1), 1)

    return {
        "total_words": total_words,
        "total_sentences": len(sentences),
        "total_cliche_hits": total_hits,
        "water_index_percent": water_index,  # чем выше — тем "водянистее" текст
        "hits_by_category": category_counts,
        "flagged_sentences": findings[:50],  # ограничиваем вывод, чтобы отчёт не разросся
    }


REWRITE_SYSTEM = """Ты — научный редактор, который приводит текст дипломной работы
к строгому академическому стилю. Тебе дают предложение с канцеляризмами/штампами/водой.
Перепиши его кратко, по делу, без потери фактического смысла (не придумывай новые факты).
Отвечай ТОЛЬКО валидным JSON: {"original": "...", "rewritten": "..."}"""


def rewrite_sentence(llm, sentence: str) -> dict:
    from llm_client import ask_json
    return ask_json(llm, REWRITE_SYSTEM, sentence)


def rewrite_flagged_sentences(llm, flagged_sentences: list, limit: int = 10) -> list:
    """
    Переписывает первые `limit` найденных "грязных" предложений через LLM.
    Ограничение по числу вызовов — чтобы не пересылать в API весь диплом предложение за предложением.
    """
    results = []
    for item in flagged_sentences[:limit]:
        try:
            rewritten = rewrite_sentence(llm, item["sentence"])
            results.append({
                "category": item["category"],
                "original": rewritten.get("original", item["sentence"]),
                "rewritten": rewritten.get("rewritten"),
            })
        except Exception as e:
            results.append({
                "category": item["category"],
                "original": item["sentence"],
                "rewritten": None,
                "error": str(e),
            })
    return results


if __name__ == "__main__":
    sample = (
        "На сегодняшний день актуальность данной темы обусловлена тем, что в современном мире "
        "нельзя не отметить важную роль цифровизации. Следует отметить, что данная работа "
        "представляет собой уникальную методику анализа."
    )
    import json
    print(json.dumps(analyze_water_level(sample), ensure_ascii=False, indent=2))
