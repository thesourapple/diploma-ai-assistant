"""Сборка человекочитаемого Markdown-отчёта из результатов всех трёх уровней анализа."""

from __future__ import annotations

from .analyzer import LogicReport, StructuralReport, StyleReport
from .parser import ParsedDocument


def _severity_icon(severity: str) -> str:
    return "🔴" if severity == "critical" else "🟡"


def build_markdown_report(
    doc: ParsedDocument,
    structural: StructuralReport,
    logic: LogicReport | None,
    style: StyleReport,
) -> str:
    lines: list[str] = []
    lines.append(f"# Отчёт по анализу дипломной работы\n")
    lines.append(f"**Файл:** `{doc.source_path}`  ")
    lines.append(f"**Разделов найдено:** {len(doc.sections)}  ")
    lines.append(f"**Всего слов:** {sum(s.word_count for s in doc.sections)}\n")

    # --- KPI сводка ---
    lines.append("## 📊 KPI сводка\n")
    critical_count = sum(1 for i in structural.issues if i.severity == "critical")
    warning_count = sum(1 for i in structural.issues if i.severity == "warning")
    lines.append(f"- Критических структурных проблем: **{critical_count}**")
    lines.append(f"- Предупреждений по структуре: **{warning_count}**")
    if logic:
        lines.append(f"- Соответствие цели (введение) и результата (заключение): **{logic.goal_conclusion_match_score}/100**")
    lines.append(f"- Средний процент «словесного мусора» по разделам: **{style.overall_water_percentage:.0f}%**")
    lines.append(f"- Найдено стилистических проблем всего: **{style.total_problems}**\n")

    # --- Структура ---
    lines.append("## 1. Структурная проверка\n")
    lines.append(f"- Введение: {'✅ найдено' if structural.has_intro else '❌ не найдено'}")
    lines.append(f"- Количество глав: {structural.chapter_count}")
    lines.append(f"- Заключение: {'✅ найдено' if structural.has_conclusion else '❌ не найдено'}")
    lines.append(f"- Список литературы: {'✅ найден' if structural.has_references else '❌ не найден'}\n")

    if structural.issues:
        lines.append("**Замечания:**\n")
        for issue in structural.issues:
            lines.append(f"- {_severity_icon(issue.severity)} {issue.message}")
        lines.append("")

    # --- Логика ---
    lines.append("## 2. Логическая связность (Введение ↔ Заключение)\n")
    if logic is None:
        lines.append("_Пропущено: отсутствует Введение или Заключение._\n")
    else:
        lines.append(f"**Цель работы (извлечена из введения):** {logic.goal_extracted or '_не указана явно_'}\n")
        if logic.hypothesis_extracted:
            status = {
                True: "✅ подтверждена",
                False: "❌ не подтверждена / опровергнута",
                None: "❓ статус не определён",
            }[logic.hypothesis_confirmed_in_conclusion]
            lines.append(f"**Гипотеза:** {logic.hypothesis_extracted}")
            lines.append(f"**Статус гипотезы в заключении:** {status}\n")

        if logic.tasks_addressed_in_conclusion:
            lines.append("**Задачи и их отражение в заключении:**\n")
            for t in logic.tasks_addressed_in_conclusion:
                mark = "✅" if t.get("addressed") else "❌"
                lines.append(f"- {mark} {t.get('task', '')} — {t.get('comment', '')}")
            lines.append("")

        if logic.issues:
            lines.append("**Найденные несоответствия:**\n")
            for i in logic.issues:
                lines.append(f"- 🔴 {i}")
            lines.append("")

        lines.append(f"**Вывод:** {logic.verdict}\n")

    # --- Стиль ---
    lines.append("## 3. Стилистический анализ («вода», штампы, канцеляризмы)\n")
    if not style.sections:
        lines.append("_Нет секций, подходящих для анализа._\n")
    else:
        for sec in style.sections:
            lines.append(f"### {sec.section_title}")
            lines.append(f"Оценка «воды»: **{sec.water_percentage_estimate}%** — {sec.section_verdict}\n")
            if sec.problems:
                for p in sec.problems:
                    lines.append(f"- **[{p.get('type', '?')}]** «{p.get('quote', '')}»")
                    lines.append(f"  → *Предлагаемая правка:* {p.get('suggestion', '')}")
                lines.append("")
            else:
                lines.append("_Существенных проблем не найдено._\n")

    return "\n".join(lines)
