# -*- coding: utf-8 -*-
"""
Главный скрипт: собирает весь пайплайн из трёх этапов задания.

Использование:
    export ANTHROPIC_API_KEY=sk-ant-...
    python main.py путь_к_диплому.docx --output report.md
    python main.py путь_к_диплому.docx --no-llm      # только быстрый анализ воды, без API
    python main.py путь_к_диплому.docx --rewrite      # + переписать грязные предложения через LLM
"""

import argparse
import sys
import json

from segmenter import segment_docx, segment_summary
from style_filter import analyze_water_level, rewrite_flagged_sentences
from analyzer import run_full_cross_analysis
from report_generator import build_report


def main():
    parser = argparse.ArgumentParser(description="Семантический ИИ-ассистент по улучшению дипломных работ")
    parser.add_argument("docx_path", help="Путь к .docx файлу диплома")
    parser.add_argument("--output", default="report.md", help="Куда сохранить итоговый отчёт")
    parser.add_argument("--no-llm", action="store_true", help="Только детерминированный анализ воды, без вызовов LLM")
    parser.add_argument("--rewrite", action="store_true", help="Переписать самые 'грязные' предложения через LLM")
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Название модели")
    args = parser.parse_args()

    print(f"[1/3] Сегментация документа: {args.docx_path}")
    sections = segment_docx(args.docx_path)
    print(segment_summary(sections))

    print("\n[2/3] Стилистический анализ (поиск воды/штампов)...")
    style_reports = {name: analyze_water_level(text) for name, text in sections.items()}

    cross_analysis = {"error": "LLM-анализ отключён (--no-llm)"}
    rewrites = {}

    if not args.no_llm:
        print("\n[3/3] Кросс-анализ логики через LLM (Введение ↔ Заключение)...")
        try:
            from llm_client import get_llm
            llm = get_llm(model_name=args.model)
            cross_analysis = run_full_cross_analysis(llm, sections)

            if args.rewrite:
                print("Переписываю самые 'водянистые' предложения...")
                for name, report in style_reports.items():
                    if report["flagged_sentences"]:
                        rewrites[name] = rewrite_flagged_sentences(llm, report["flagged_sentences"], limit=8)
        except Exception as e:
            print(f"⚠️ LLM-анализ не выполнен: {e}", file=sys.stderr)
            cross_analysis = {"error": str(e)}
    else:
        print("\n[3/3] Пропущено (--no-llm)")

    report_md = build_report(sections, cross_analysis, style_reports)

    if rewrites:
        report_md += "\n## 4. Предложенные исправления стиля\n"
        for name, items in rewrites.items():
            report_md += f"\n### {name}\n"
            for item in items:
                report_md += f"- **Было:** {item['original']}\n"
                report_md += f"  **Стало:** {item.get('rewritten', '(ошибка обработки)')}\n"

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"\nГотово! Отчёт сохранён в {args.output}")


if __name__ == "__main__":
    main()
