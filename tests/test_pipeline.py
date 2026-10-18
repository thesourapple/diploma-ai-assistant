"""
Тест полного пайплайна на примере docx, с моком YandexGPTClient
(не требует реальных API-ключей). Запуск:

    python -m pytest tests/ -v
    # или просто:
    python tests/test_pipeline.py
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from diploma_ai_assistant.parser import parse_docx, SectionType
from diploma_ai_assistant.analyzer import analyze_structure, analyze_logic, analyze_style
from diploma_ai_assistant.report import build_markdown_report

EXAMPLE_PATH = Path(__file__).resolve().parent.parent / "examples" / "sample_diploma.docx"


def test_parser_finds_all_sections():
    doc = parse_docx(EXAMPLE_PATH)
    types = {s.type for s in doc.sections}
    assert SectionType.INTRODUCTION in types
    assert SectionType.CHAPTER in types
    assert SectionType.CONCLUSION in types
    assert SectionType.REFERENCES in types


def test_structural_analysis_no_critical_issues_on_valid_doc():
    doc = parse_docx(EXAMPLE_PATH)
    report = analyze_structure(doc)
    critical = [i for i in report.issues if i.severity == "critical"]
    assert critical == [], f"Не должно быть критических проблем на валидном документе: {critical}"


def test_logic_and_style_with_mocked_client():
    doc = parse_docx(EXAMPLE_PATH)
    structural = analyze_structure(doc)

    mock_client = MagicMock()
    mock_client.complete_json.side_effect = [
        {
            "goal_extracted": "Тестовая цель",
            "tasks_extracted": ["задача 1"],
            "hypothesis_extracted": None,
            "hypothesis_confirmed_in_conclusion": None,
            "tasks_addressed_in_conclusion": [],
            "goal_conclusion_match_score": 80,
            "issues": [],
            "verdict": "Ок.",
        },
        *[{"water_percentage_estimate": 0, "problems": [], "section_verdict": "ок"} for _ in range(10)],
    ]

    logic = analyze_logic(mock_client, doc)
    style = analyze_style(mock_client, doc)

    assert logic is not None
    assert logic.goal_conclusion_match_score == 80
    assert style.sections  # хотя бы одна секция проанализирована

    report_md = build_markdown_report(doc, structural, logic, style)
    assert "KPI сводка" in report_md
    assert "Логическая связность" in report_md


def test_ai_studio_client_requires_credentials():
    from diploma_ai_assistant import YandexAIStudioClient
    import os

    saved = {k: os.environ.pop(k, None) for k in ("YANDEX_API_KEY", "YANDEX_FOLDER_ID", "YANDEX_AGENT_PROMPT_ID")}
    try:
        raised = False
        try:
            YandexAIStudioClient()
        except ValueError:
            raised = True
        assert raised, "Без ключей конструктор должен поднимать ValueError"
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_ai_studio_client_ask_agent_without_prompt_id():
    from diploma_ai_assistant import YandexAIStudioClient

    client = YandexAIStudioClient(api_key="fake", folder_id="fake_folder")
    raised = False
    try:
        client.ask_agent("привет")
    except ValueError:
        raised = True
    assert raised, "Без prompt_id ask_agent() должен поднимать ValueError"


if __name__ == "__main__":
    test_parser_finds_all_sections()
    test_structural_analysis_no_critical_issues_on_valid_doc()
    test_logic_and_style_with_mocked_client()
    test_ai_studio_client_requires_credentials()
    test_ai_studio_client_ask_agent_without_prompt_id()
    print("Все тесты пройдены успешно ✅")
