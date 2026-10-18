"""Смысловой ИИ-ассистент по улучшению дипломных работ."""

from .parser import parse_docx, ParsedDocument, Section, SectionType
from .analyzer import analyze_structure, analyze_logic, analyze_style
from .yandex_client import YandexGPTClient, YandexAIStudioClient
from .report import build_markdown_report

__all__ = [
    "parse_docx", "ParsedDocument", "Section", "SectionType",
    "analyze_structure", "analyze_logic", "analyze_style",
    "YandexGPTClient", "YandexAIStudioClient", "build_markdown_report",
]
