# -*- coding: utf-8 -*-
"""
Этап 1: Сегментация документа.

Задача: жёстко разбить .docx на Введение / Главы / Заключение / Список литературы,
не полагаясь на LLM (это должно быть детерминированным парсингом,
иначе на 30-60 страницах будут галлюцинации и на этапе разметки).

Логика:
  - Заголовок определяется ЛИБО стилем параграфа (Heading 1 / Заголовок 1),
    ЛИБО короткой строкой, совпадающей с регуляркой из config.SECTION_PATTERNS.
  - Весь текст между двумя заголовками относится к разделу, который открыл
    предыдущий заголовок.
"""

import re
from docx import Document
from config import SECTION_PATTERNS


def classify_heading(text: str):
    """Возвращает имя раздела, если строка похожа на заголовок раздела диплома."""
    t = text.strip().lower()
    for pattern, name in SECTION_PATTERNS:
        if re.match(pattern, t, re.IGNORECASE):
            return name
    return None


def is_heading_style(paragraph) -> bool:
    """Проверяет, размечен ли параграф в Word как заголовок."""
    style_name = (paragraph.style.name or "").lower()
    return style_name.startswith("heading") or style_name.startswith("заголовок") or style_name.startswith("title")


def segment_docx(path: str) -> dict:
    """
    Разбирает .docx файл и возвращает словарь:
        {"Введение": "...текст...", "Глава 1": "...", "Заключение": "...", ...}

    Если раздел не распознан, весь текст до первого заголовка попадает в
    "Прочее/Не определено" (например, титульный лист, содержание).
    """
    doc = Document(path)

    sections = {}
    current = "Прочее/Не определено"
    sections[current] = []

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue

        heading_name = classify_heading(text)

        # Заголовком считаем короткую строку, похожую на паттерн раздела,
        # ЛИБО строку с Word-стилем заголовка (даже если она чуть длиннее,
        # например "Глава 1. Теоретические основы анализа рисков")
        if heading_name and (is_heading_style(p) or len(text) < 80):
            current = heading_name
            sections.setdefault(current, [])
            continue

        sections.setdefault(current, []).append(text)

    # Склеиваем абзацы в единый текст раздела
    result = {name: "\n".join(paragraphs) for name, paragraphs in sections.items() if paragraphs}
    return result


def segment_summary(sections: dict) -> str:
    """Короткая человекочитаемая сводка: сколько слов в каждом разделе."""
    lines = ["Найденные разделы документа:"]
    for name, text in sections.items():
        word_count = len(text.split())
        lines.append(f"  - {name}: {word_count} слов")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Использование: python segmenter.py путь_к_диплому.docx")
        sys.exit(1)
    secs = segment_docx(sys.argv[1])
    print(segment_summary(secs))
