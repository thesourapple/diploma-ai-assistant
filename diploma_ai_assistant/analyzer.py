"""
Аналитическое ядро.

Три уровня анализа:

1. structural   — чисто правиловая проверка (есть ли Введение/Главы/Заключение/
                   Список литературы, не перепутан ли порядок, не пропущено ли что-то).
                   Не требует ИИ — работает мгновенно и бесплатно.

2. logic        — кросс-анализ через LLM: сравнение целей/задач из Введения
                   с тем, что реально сделано в Заключении; проверка, что
                   гипотеза (если заявлена) была подтверждена или опровергнута.

3. style        — детекция "воды", канцеляризмов, пустых рассуждений на уровне
                   каждой секции (Map), с последующей сборкой сводного отчёта (Reduce).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .parser import ParsedDocument, Section, SectionType
from .yandex_client import YandexGPTClient

# ---------------------------------------------------------------------------
# 1. Структурная проверка (без ИИ)
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = [
    SectionType.INTRODUCTION,
    SectionType.CHAPTER,
    SectionType.CONCLUSION,
    SectionType.REFERENCES,
]


@dataclass
class StructuralIssue:
    severity: str  # "critical" | "warning"
    message: str


@dataclass
class StructuralReport:
    issues: list[StructuralIssue] = field(default_factory=list)
    has_intro: bool = False
    has_conclusion: bool = False
    chapter_count: int = 0
    has_references: bool = False

    def add(self, severity: str, message: str) -> None:
        self.issues.append(StructuralIssue(severity, message))


def analyze_structure(doc: ParsedDocument) -> StructuralReport:
    report = StructuralReport()

    intros = doc.get(SectionType.INTRODUCTION)
    conclusions = doc.get(SectionType.CONCLUSION)
    chapters = doc.get(SectionType.CHAPTER)
    references = doc.get(SectionType.REFERENCES)

    report.has_intro = bool(intros)
    report.has_conclusion = bool(conclusions)
    report.chapter_count = len(chapters)
    report.has_references = bool(references)

    if not intros:
        report.add("critical", "Раздел «Введение» не найден.")
    elif intros[0].word_count < 150:
        report.add("warning", f"«Введение» очень короткое ({intros[0].word_count} слов) — "
                               f"возможно, не раскрыты актуальность, цель, задачи, объект и предмет.")

    if not chapters:
        report.add("critical", "Ни одной главы/раздела основной части не найдено.")
    elif len(chapters) == 1:
        report.add("warning", "Найдена только одна глава — для дипломной работы обычно ожидается "
                               "минимум 2 (теоретическая + практическая/аналитическая).")

    if not conclusions:
        report.add("critical", "Раздел «Заключение» не найден.")
    elif conclusions[0].word_count < 100:
        report.add("warning", f"«Заключение» очень короткое ({conclusions[0].word_count} слов) — "
                               f"вероятно, не подведены итоги по каждой задаче из введения.")

    if not references:
        report.add("critical", "Раздел «Список литературы/источников» не найден.")

    # порядок разделов: введение должно быть раньше заключения
    order = [s.type for s in doc.sections]
    if SectionType.INTRODUCTION in order and SectionType.CONCLUSION in order:
        if order.index(SectionType.INTRODUCTION) > order.index(SectionType.CONCLUSION):
            report.add("critical", "«Введение» расположено после «Заключения» — нарушен порядок разделов.")

    return report


# ---------------------------------------------------------------------------
# 2. Кросс-анализ логики через LLM
# ---------------------------------------------------------------------------

_LOGIC_SYSTEM_PROMPT = """\
Ты — опытный научный руководитель, проверяющий дипломные и выпускные квалификационные работы.
Тебе дают текст «Введения» и текст «Заключения» одной и той же работы.
Твоя задача — строго и по делу оценить логическую связность работы.

Отвечай ТОЛЬКО валидным JSON без markdown-обёртки, со следующей структурой:
{
  "goal_extracted": "краткая формулировка цели работы из Введения (или null, если не указана)",
  "tasks_extracted": ["список задач из Введения, если перечислены"],
  "hypothesis_extracted": "гипотеза, если заявлена в тексте, иначе null",
  "hypothesis_confirmed_in_conclusion": true | false | null,
  "tasks_addressed_in_conclusion": [
    {"task": "формулировка задачи", "addressed": true|false, "comment": "короткий комментарий"}
  ],
  "goal_conclusion_match_score": 0-100,
  "issues": ["конкретные найденные несоответствия между введением и заключением"],
  "verdict": "1-2 предложения общего вывода"
}
Будь конкретным и придирчивым: если задача из введения не упомянута в заключении явно или неявно — отметь это.
"""


@dataclass
class LogicReport:
    goal_extracted: Optional[str]
    tasks_extracted: list[str]
    hypothesis_extracted: Optional[str]
    hypothesis_confirmed_in_conclusion: Optional[bool]
    tasks_addressed_in_conclusion: list[dict]
    goal_conclusion_match_score: int
    issues: list[str]
    verdict: str
    raw: dict


def analyze_logic(client: YandexGPTClient, doc: ParsedDocument) -> Optional[LogicReport]:
    intros = doc.get(SectionType.INTRODUCTION)
    conclusions = doc.get(SectionType.CONCLUSION)
    if not intros or not conclusions:
        return None

    intro_text = "\n\n".join(s.text for s in intros)
    conclusion_text = "\n\n".join(s.text for s in conclusions)

    user_prompt = (
        f"ТЕКСТ ВВЕДЕНИЯ:\n{intro_text}\n\n"
        f"ТЕКСТ ЗАКЛЮЧЕНИЯ:\n{conclusion_text}\n\n"
        "Проанализируй согласно инструкции и верни JSON."
    )

    data = client.complete_json(_LOGIC_SYSTEM_PROMPT, user_prompt, max_tokens=1500)

    return LogicReport(
        goal_extracted=data.get("goal_extracted"),
        tasks_extracted=data.get("tasks_extracted", []) or [],
        hypothesis_extracted=data.get("hypothesis_extracted"),
        hypothesis_confirmed_in_conclusion=data.get("hypothesis_confirmed_in_conclusion"),
        tasks_addressed_in_conclusion=data.get("tasks_addressed_in_conclusion", []) or [],
        goal_conclusion_match_score=int(data.get("goal_conclusion_match_score", 0) or 0),
        issues=data.get("issues", []) or [],
        verdict=data.get("verdict", ""),
        raw=data,
    )


# ---------------------------------------------------------------------------
# 3. Стилистический фильтр ("вода", канцеляризмы) — Map-Reduce по секциям
# ---------------------------------------------------------------------------

_STYLE_SYSTEM_PROMPT = """\
Ты — редактор академических текстов (уровень «Главред»). Тебе дают один раздел
дипломной работы. Найди:
  - канцеляризмы и штампы ("данная работа посвящена", "в настоящее время особую
    актуальность приобретает", "необходимо отметить, что" и подобные);
  - "воду" — предложения, не несущие фактической информации;
  - пустые рассуждения без опоры на факты/источники;
  - излишне длинные, перегруженные придаточными предложения.

Отвечай ТОЛЬКО валидным JSON без markdown-обёртки:
{
  "water_percentage_estimate": 0-100,
  "problems": [
    {"quote": "короткая цитата проблемного фрагмента (до 20 слов)", "type": "штамп|вода|канцеляризм|пустое_рассуждение", "suggestion": "как перефразировать в строгом академическом стиле"}
  ],
  "section_verdict": "1 предложение общей оценки раздела"
}
Если раздел короткий или чистый — верни пустой список problems и низкий процент.
"""


@dataclass
class SectionStyleReport:
    section_title: str
    section_type: SectionType
    water_percentage_estimate: int
    problems: list[dict]
    section_verdict: str


@dataclass
class StyleReport:
    sections: list[SectionStyleReport] = field(default_factory=list)

    @property
    def overall_water_percentage(self) -> float:
        if not self.sections:
            return 0.0
        return sum(s.water_percentage_estimate for s in self.sections) / len(self.sections)

    @property
    def total_problems(self) -> int:
        return sum(len(s.problems) for s in self.sections)


def analyze_style(
    client: YandexGPTClient,
    doc: ParsedDocument,
    min_words: int = 40,
    max_sections: Optional[int] = None,
) -> StyleReport:
    """
    Map: анализируем каждую содержательную секцию отдельно (чтобы не превышать
    контекст модели на 30-60-страничных документах).
    Reduce: собираем в единый StyleReport, агрегированные метрики считаются лениво (properties).
    """
    report = StyleReport()

    candidates = [
        s for s in doc.sections
        if s.type not in (SectionType.REFERENCES, SectionType.APPENDIX)
        and s.word_count >= min_words
    ]
    if max_sections:
        candidates = candidates[:max_sections]

    for section in candidates:
        user_prompt = f"РАЗДЕЛ: {section.title}\n\nТЕКСТ:\n{section.text}"
        try:
            data = client.complete_json(_STYLE_SYSTEM_PROMPT, user_prompt, max_tokens=1200)
        except Exception as exc:  # noqa: BLE001 — не даём одному сбою уронить весь отчёт
            data = {
                "water_percentage_estimate": 0,
                "problems": [],
                "section_verdict": f"Не удалось проанализировать раздел: {exc}",
            }

        report.sections.append(
            SectionStyleReport(
                section_title=section.title,
                section_type=section.type,
                water_percentage_estimate=int(data.get("water_percentage_estimate", 0) or 0),
                problems=data.get("problems", []) or [],
                section_verdict=data.get("section_verdict", ""),
            )
        )

    return report
