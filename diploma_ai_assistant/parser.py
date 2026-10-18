"""
Модуль сегментации дипломной работы (.docx) на структурные разделы.

Логика:
1. Читаем документ через python-docx.
2. Идём по параграфам, определяем "заголовочность" параграфа двумя способами:
   - по стилю (Heading 1 / Heading 2 / Заголовок 1 / Title и т.п.)
   - по regex-паттерну текста (ВВЕДЕНИЕ, ГЛАВА 1, ЗАКЛЮЧЕНИЕ, СПИСОК ЛИТЕРАТУРЫ, ...)
     — это нужно, т.к. многие студенты не пользуются стилями Word, а просто
     жирным шрифтом и заглавными буквами оформляют "заголовок".
3. Каждый заголовок открывает новую секцию; весь текст до следующего заголовка
   складывается в эту секцию.
4. Секции классифицируются по типу (SectionType) через сопоставление с
   словарём синонимов.

Результат — Document dataclass с списком Section (type, title, paragraphs, raw_text).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from docx import Document as _DocxDocument


class SectionType(str, Enum):
    TITLE_PAGE = "title_page"
    INTRODUCTION = "introduction"
    CHAPTER = "chapter"
    CONCLUSION = "conclusion"
    REFERENCES = "references"
    APPENDIX = "appendix"
    UNKNOWN = "unknown"


# Паттерны заголовков -> тип секции. Порядок важен: более специфичные первыми.
_HEADING_PATTERNS: list[tuple[re.Pattern, SectionType]] = [
    (re.compile(r"^\s*ВВЕДЕНИЕ\s*$", re.IGNORECASE), SectionType.INTRODUCTION),
    (re.compile(r"^\s*ЗАКЛЮЧЕНИЕ\s*$", re.IGNORECASE), SectionType.CONCLUSION),
    (re.compile(r"^\s*(СПИСОК\s+(ИСПОЛЬЗОВАННЫХ\s+)?(ИСТОЧНИКОВ|ЛИТЕРАТУРЫ))", re.IGNORECASE), SectionType.REFERENCES),
    (re.compile(r"^\s*(БИБЛИОГРАФИЧЕСКИЙ\s+СПИСОК)", re.IGNORECASE), SectionType.REFERENCES),
    (re.compile(r"^\s*ПРИЛОЖЕНИЕ", re.IGNORECASE), SectionType.APPENDIX),
    (re.compile(r"^\s*ГЛАВА\s*\d+", re.IGNORECASE), SectionType.CHAPTER),
    (re.compile(r"^\s*\d+(\.\d+)?\s+[А-ЯA-Z]", re.IGNORECASE), SectionType.CHAPTER),  # "1 Обзор литературы"
]

_HEADING_STYLE_RE = re.compile(r"(heading|title|заголовок|подзаголовок)", re.IGNORECASE)

# Если заголовок короче этого числа символов и написан ЗАГЛАВНЫМИ — тоже кандидат
_MAX_HEADING_LEN = 120


@dataclass
class Section:
    type: SectionType
    title: str
    paragraphs: list[str] = field(default_factory=list)
    level: int = 1  # 1 = верхнеуровневый раздел, 2 = подраздел главы

    @property
    def text(self) -> str:
        return "\n".join(self.paragraphs)

    @property
    def word_count(self) -> int:
        return len(self.text.split())


@dataclass
class ParsedDocument:
    source_path: str
    sections: list[Section] = field(default_factory=list)

    def get(self, section_type: SectionType) -> list[Section]:
        return [s for s in self.sections if s.type == section_type]

    def full_text(self) -> str:
        return "\n\n".join(s.text for s in self.sections)

    def summary(self) -> str:
        lines = [f"Документ: {self.source_path}", f"Найдено секций: {len(self.sections)}"]
        for s in self.sections:
            lines.append(f"  [{s.type.value:12}] {s.title[:60]!r:65} ~{s.word_count} слов")
        return "\n".join(lines)


def _is_heading_by_style(paragraph) -> bool:
    style_name = getattr(paragraph.style, "name", "") or ""
    return bool(_HEADING_STYLE_RE.search(style_name))


def _is_heading_by_shape(text: str, paragraph) -> bool:
    """Эвристика для документов без стилей: короткая строка, много КАПСА или жирный шрифт целиком."""
    stripped = text.strip()
    if not stripped or len(stripped) > _MAX_HEADING_LEN:
        return False
    letters = [c for c in stripped if c.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(c.isupper() for c in letters) / len(letters)
    if upper_ratio > 0.8 and len(stripped.split()) <= 12:
        return True
    # весь параграф жирным и короткий — тоже похоже на заголовок
    runs = [r for r in paragraph.runs if r.text.strip()]
    if runs and all(r.bold for r in runs) and len(stripped.split()) <= 12:
        return True
    return False


def _classify_heading(text: str) -> SectionType:
    for pattern, sec_type in _HEADING_PATTERNS:
        if pattern.search(text.strip()):
            return sec_type
    return SectionType.UNKNOWN


def parse_docx(path: str | Path) -> ParsedDocument:
    path = str(path)
    doc = _DocxDocument(path)

    parsed = ParsedDocument(source_path=path)
    current: Optional[Section] = None
    seen_first_heading = False

    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue

        is_heading = _is_heading_by_style(paragraph) or _is_heading_by_shape(text, paragraph)

        if is_heading:
            sec_type = _classify_heading(text)
            # До первого распознанного заголовка — считаем титульным/техническим блоком
            current = Section(type=sec_type, title=text)
            parsed.sections.append(current)
            seen_first_heading = True
            continue

        if current is None:
            # Текст до первого заголовка — титульная страница / аннотация
            current = Section(type=SectionType.TITLE_PAGE, title="(до первого заголовка)")
            parsed.sections.append(current)

        current.paragraphs.append(text)

    return parsed


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Использование: python parser.py <путь_к_файлу.docx>")
        sys.exit(1)

    result = parse_docx(sys.argv[1])
    print(result.summary())
