# Смысловой ИИ-ассистент по улучшению дипломных работ

Python-прототип инструмента, который:

1. **Парсит** черновик диплома (`.docx`) и делит его на разделы: Введение,
   Главы, Заключение, Список литературы (модуль `parser.py`).
2. **Проверяет структуру** без ИИ: все ли обязательные разделы на месте,
   не перепутан ли порядок (модуль `analyzer.py`, функция `analyze_structure`).
3. **Кросс-анализирует логику** через YandexGPT: соответствует ли заключение
   целям и задачам из введения, подтверждена ли гипотеза (`analyze_logic`).
4. **Ищет "воду"**, канцеляризмы и штампы по каждому разделу и предлагает
   правки в академическом стиле (`analyze_style`, Map-Reduce по секциям).
5. **Собирает итоговый Markdown-отчёт** с KPI-метриками (`report.py`).

Проект сделан во время производственной практики в Центре прикладных исследований
и разработок ДВФУ (июнь–июль 2026).

## Две версии

- **Основная (корень репозитория, `diploma_ai_assistant/`)** — YandexGPT через
  Foundation Models API и Responses API (Yandex AI Studio), CLI `analyze` / `agent`,
  тесты с mock-клиентом.
- **`langchain_version/`** — альтернативный прототип на LangChain: сегментация
  на регулярных выражениях, rule-based метрика «воды» по словарю штампов и
  канцеляризмов (работает без LLM, флаг `--no-llm`), сверка введения и
  заключения через LLM. Подробности — в `langchain_version/README.md`.

## Установка

```bash
pip install -r requirements.txt
```

## ⚠️ Безопасность API-ключа

Никогда не хардкодьте `YANDEX_API_KEY` в коде и не публикуйте его в чатах,
issue-трекерах, скриншотах и т.п. Ключ — это полный доступ к вашему биллингу
Yandex Cloud. Если ключ где-то "засветился" — зайдите в Yandex Cloud →
Service accounts → API keys и немедленно отозовите/пересоздайте его.
Храните ключ только в переменных окружения или секрет-менеджере.

## Два способа доступа к Yandex AI Studio

Проект поддерживает оба API Yandex AI Studio — они решают разные задачи:

| | `YandexGPTClient` (Foundation Models API) | `YandexAIStudioClient` (Responses API) |
|---|---|---|
| Что вызывает | "сырую" модель напрямую | сохранённого агента из **Agent Atelier** (или модель напрямую) |
| Формат ответа | строгий JSON (нужен для KPI-пайплайна) | свободный текст, как настроено в агенте |
| Где используется | команда `analyze` | команда `agent` |
| Endpoint | `llm.api.cloud.yandex.net` | `ai.api.cloud.yandex.net/v1` (OpenAI-совместимый) |

### Настройка переменных окружения

```bash
export YANDEX_API_KEY="AQVN..."          # API-ключ сервисного аккаунта
export YANDEX_FOLDER_ID="b1g..."         # id каталога (folder / project)

# Только для команды `agent` — id агента, сохранённого в Agent Atelier
# (его видно в интерфейсе AI Studio на странице агента, это то же самое
# значение, что передаётся в prompt={"id": ...} в Responses API)
export YANDEX_AGENT_PROMPT_ID="<id_вашего_агента>"
```

(Вместо `YANDEX_API_KEY` в `YandexGPTClient` можно использовать `YANDEX_IAM_TOKEN`.)

## Использование

```bash
# --- Команда analyze: полный JSON-пайплайн (структура + логика + стиль) ---

python -m diploma_ai_assistant.cli analyze путь/к/диплому.docx

# Только структурная проверка, без вызовов ИИ и без ключей
python -m diploma_ai_assistant.cli analyze путь/к/диплому.docx --no-ai

# Ограничить число секций для стилевого анализа (быстрый тест на большом файле)
python -m diploma_ai_assistant.cli analyze путь/к/диплому.docx --max-sections 3

# Указать путь для отчёта
python -m diploma_ai_assistant.cli analyze путь/к/диплому.docx --out my_report.md


# --- Команда agent: отправить документ сохранённому агенту (Responses API) ---

# Весь документ целиком
python -m diploma_ai_assistant.cli agent путь/к/диплому.docx

# Только раздел, в заголовке которого встречается подстрока
python -m diploma_ai_assistant.cli agent путь/к/диплому.docx --section введение

python -m diploma_ai_assistant.cli agent путь/к/диплому.docx --out answer.md
```

`analyze` даёт Markdown-файл `<имя_файла>_report.md` со сводкой KPI, списком
структурных проблем, кросс-анализом введения/заключения и построчными
правками по стилю. `agent` даёт `<имя_файла>_agent_answer.md` — свободный
текстовый разбор от вашего агента, настроенного в Agent Atelier.

## Использование как библиотеки

```python
from diploma_ai_assistant import (
    parse_docx, analyze_structure, analyze_logic, analyze_style,
    YandexGPTClient, YandexAIStudioClient, build_markdown_report,
)

doc = parse_docx("diploma.docx")
structural = analyze_structure(doc)

# Вариант 1: JSON-пайплайн через "сырой" Foundation Models API
client = YandexGPTClient()  # читает YANDEX_API_KEY / YANDEX_FOLDER_ID из окружения
logic = analyze_logic(client, doc)
style = analyze_style(client, doc)
report_md = build_markdown_report(doc, structural, logic, style)
print(report_md)

# Вариант 2: вызов сохранённого агента через Responses API
agent_client = YandexAIStudioClient()  # + YANDEX_AGENT_PROMPT_ID из окружения
answer_text, response_id = agent_client.ask_agent(doc.full_text())
print(answer_text)

# Продолжение диалога с сохранением контекста (без threads — через previous_response_id)
followup_text, _ = agent_client.ask_agent(
    "Уточни, пожалуйста, что именно не так с гипотезой",
    previous_response_id=response_id,
)
```

## Структура проекта

```
diploma_ai_assistant/
├── diploma_ai_assistant/
│   ├── __init__.py
│   ├── parser.py         # сегментация .docx на разделы (регэксп + стили Word)
│   ├── yandex_client.py  # клиент YandexGPT (Yandex Cloud Foundation Models)
│   ├── analyzer.py       # структурная проверка + логика + стиль (LLM)
│   ├── report.py         # сборка Markdown-отчёта
│   └── cli.py            # точка входа командной строки
├── examples/
│   └── sample_diploma.docx
├── tests/
│   └── test_pipeline.py
├── langchain_version/    # альтернативный прототип на LangChain
├── requirements.txt
└── README.md
```

## Тесты

```bash
pip install pytest
python -m pytest tests
```

Тесты не обращаются к API: LLM подменяется mock-клиентом.

## Как устроен парсер (без ИИ)

Многие студенческие работы не используют встроенные стили заголовков Word,
поэтому `parser.py` определяет заголовок разделa двумя способами:

- по стилю параграфа (`Heading 1`, `Заголовок 1`, ...);
- по форме текста: короткая строка, написанная КАПСОМ, или строка,
  целиком набранная жирным шрифтом (эвристика `_is_heading_by_shape`).

Затем заголовок классифицируется по regex-словарю
(`ВВЕДЕНИЕ`, `ГЛАВА \d+`, `ЗАКЛЮЧЕНИЕ`, `СПИСОК ЛИТЕРАТУРЫ`, `ПРИЛОЖЕНИЕ`).

## Ограничения текущего прототипа

- YandexGPT имеет ограниченное контекстное окно — для очень длинных глав
  (>10-15 страниц одной главы) может потребоваться дополнительное разбиение
  внутри `analyze_style` (сейчас режется по секциям, но не внутри них).
- Хорошо бы добавить сравнение оглавления с фактической структурой документа.
- Оценка "процента воды" — это оценка LLM, а не формальная метрика; для
  строгого KPI стоит дополнительно интегрировать внешний сервис типа
  Главред API, как и было заявлено в концепции.
- Детекция заголовков через КАПС/жирный шрифт — эвристика; на документах
  с нестандартным оформлением возможны ложные срабатывания — стоит визуально
  проверять `summary()` перед полным AI-анализом.
