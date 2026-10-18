# -*- coding: utf-8 -*-
"""
Собирает результаты всех этапов в единый читаемый Markdown-отчёт.
"""


def build_report(sections: dict, cross_analysis: dict, style_reports: dict) -> str:
    lines = []
    lines.append("# Отчёт по анализу дипломной работы\n")

    # --- Раздел 1: структура документа ---
    lines.append("## 1. Структура документа\n")
    for name, text in sections.items():
        lines.append(f"- **{name}** — {len(text.split())} слов")
    lines.append("")

    # --- Раздел 2: логическая связность ---
    lines.append("## 2. Логическая связность (Введение ↔ Заключение)\n")
    if "error" in cross_analysis:
        lines.append(f"⚠️ {cross_analysis['error']}\n")
    else:
        verdict = cross_analysis["verdict"]
        lines.append(f"**Общая оценка логики: {verdict.get('overall_logic_score', '?')}/10**\n")
        lines.append(f"**Соответствие цели и результатов:** {verdict.get('goal_vs_results_match')}\n")

        lines.append("### Проверка задач из Введения\n")
        for obj in verdict.get("objectives_check", []):
            lines.append(f"- [{obj.get('status')}] {obj.get('objective')} — _{obj.get('comment')}_")
        lines.append("")

        hyp = verdict.get("hypothesis_check", {})
        lines.append("### Проверка гипотезы\n")
        lines.append(f"- Статус: **{hyp.get('status')}**")
        lines.append(f"- Комментарий: {hyp.get('comment')}\n")

        red_flags = verdict.get("red_flags", [])
        if red_flags:
            lines.append("### 🚩 Найденные логические нестыковки\n")
            for flag in red_flags:
                lines.append(f"- {flag}")
            lines.append("")

    # --- Раздел 3: стилистика / вода ---
    lines.append("## 3. Стилистический анализ ('вода' и штампы)\n")
    for section_name, report in style_reports.items():
        lines.append(f"### {section_name}")
        lines.append(f"- Индекс воды: **{report['water_index_percent']}%** "
                      f"({report['total_cliche_hits']} штампов на {report['total_sentences']} предложений)")
        for cat, count in report["hits_by_category"].items():
            if count:
                lines.append(f"  - {cat}: {count}")
        lines.append("")

    return "\n".join(lines)
