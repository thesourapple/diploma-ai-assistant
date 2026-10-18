"""
CLI: python -m diploma_ai_assistant.cli путь/к/диплому.docx [--out отчет.md] [--no-ai]

Переменные окружения для YandexGPT:
  YANDEX_API_KEY   — API-ключ сервисного аккаунта (или YANDEX_IAM_TOKEN)
  YANDEX_FOLDER_ID — id каталога в Yandex Cloud
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analyzer import analyze_logic, analyze_structure, analyze_style
from .parser import parse_docx
from .report import build_markdown_report
from .yandex_client import YandexAIStudioClient, YandexGPTClient, YandexGPTError


def _cmd_analyze(args: argparse.Namespace) -> int:
    """Полный пайплайн: структура + кросс-анализ логики + стиль, JSON-based (yandex_client.YandexGPTClient)."""
    docx_path = Path(args.docx_path)
    if not docx_path.exists():
        print(f"Файл не найден: {docx_path}", file=sys.stderr)
        return 1

    print(f"[1/4] Парсинг документа {docx_path} ...")
    doc = parse_docx(docx_path)
    print(doc.summary())

    print("[2/4] Структурная проверка ...")
    structural = analyze_structure(doc)

    logic_report = None
    style_report = None

    if args.no_ai:
        print("[3/4] Пропуск AI-анализа (--no-ai)")
        from .analyzer import StyleReport
        style_report = StyleReport()
    else:
        try:
            client = YandexGPTClient()
        except ValueError as exc:
            print(f"Не настроен доступ к YandexGPT: {exc}", file=sys.stderr)
            print("Запустите с --no-ai для проверки только структуры, "
                  "либо задайте YANDEX_API_KEY и YANDEX_FOLDER_ID.", file=sys.stderr)
            return 1

        print("[3/4] Кросс-анализ логики (Введение ↔ Заключение) через YandexGPT ...")
        try:
            logic_report = analyze_logic(client, doc)
        except YandexGPTError as exc:
            print(f"  Ошибка при анализе логики: {exc}", file=sys.stderr)

        print("[4/4] Стилистический анализ разделов через YandexGPT ...")
        style_report = analyze_style(client, doc, max_sections=args.max_sections)

    report_text = build_markdown_report(doc, structural, logic_report, style_report)

    out_path = Path(args.out) if args.out else docx_path.with_name(docx_path.stem + "_report.md")
    out_path.write_text(report_text, encoding="utf-8")
    print(f"\nОтчёт сохранён: {out_path}")
    return 0


def _cmd_agent(args: argparse.Namespace) -> int:
    """
    Отправить весь текст диплома (или отдельного раздела) сохранённому в Agent
    Atelier агенту через Responses API — без структурированного JSON-пайплайна,
    просто получить развёрнутый текстовый разбор от агента, как он настроен в UI.
    """
    docx_path = Path(args.docx_path)
    if not docx_path.exists():
        print(f"Файл не найден: {docx_path}", file=sys.stderr)
        return 1

    doc = parse_docx(docx_path)
    print(doc.summary())

    if args.section:
        matches = [s for s in doc.sections if args.section.lower() in s.title.lower()]
        if not matches:
            print(f"Раздел, содержащий {args.section!r}, не найден.", file=sys.stderr)
            return 1
        text_to_send = "\n\n".join(f"### {s.title}\n{s.text}" for s in matches)
    else:
        text_to_send = "\n\n".join(f"### {s.title}\n{s.text}" for s in doc.sections)

    try:
        client = YandexAIStudioClient()
    except (ValueError, ImportError) as exc:
        print(f"Не настроен доступ к Yandex AI Studio: {exc}", file=sys.stderr)
        print("Задайте YANDEX_API_KEY, YANDEX_FOLDER_ID, YANDEX_AGENT_PROMPT_ID.", file=sys.stderr)
        return 1

    print("Отправляю текст агенту ...")
    answer_text, response_id = client.ask_agent(text_to_send)

    out_path = Path(args.out) if args.out else docx_path.with_name(docx_path.stem + "_agent_answer.md")
    out_path.write_text(answer_text, encoding="utf-8")
    print(f"\nОтвет агента (response_id={response_id}) сохранён: {out_path}\n")
    print(answer_text)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Смысловой ИИ-ассистент по улучшению дипломных работ")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_analyze = subparsers.add_parser(
        "analyze", help="Полный JSON-пайплайн: структура + логика + стиль (YandexGPT Foundation Models API)"
    )
    p_analyze.add_argument("docx_path", help="Путь к .docx файлу дипломной работы")
    p_analyze.add_argument("--out", default=None, help="Куда сохранить отчёт (по умолчанию <файл>_report.md)")
    p_analyze.add_argument("--no-ai", action="store_true", help="Только структурная проверка, без вызовов YandexGPT")
    p_analyze.add_argument("--max-sections", type=int, default=None,
                            help="Ограничить число секций для стилевого анализа (для быстрого теста)")
    p_analyze.set_defaults(func=_cmd_analyze)

    p_agent = subparsers.add_parser(
        "agent", help="Отправить документ сохранённому агенту из Agent Atelier (Responses API)"
    )
    p_agent.add_argument("docx_path", help="Путь к .docx файлу дипломной работы")
    p_agent.add_argument("--section", default=None,
                          help="Отправить только раздел(ы), в заголовке которых встречается эта подстрока "
                               "(например: 'введение'). По умолчанию отправляется весь документ.")
    p_agent.add_argument("--out", default=None, help="Куда сохранить ответ агента")
    p_agent.set_defaults(func=_cmd_agent)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
