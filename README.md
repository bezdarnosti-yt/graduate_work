# Анализатор конфликтов в функциональных требованиях

Инструмент для автоматического обнаружения семантических конфликтов в наборах функциональных требований, записанных в нотации **EARS** (Easy Approach to Requirements Syntax).

## Описание

Система обрабатывает текстовые требования, извлекает из них сущности с помощью NLP, строит граф знаний на основе онтологии OWL/RDF и выявляет противоречия двумя способами:

- **Анализ по правилам** — быстрая попарная проверка нормализованных требований без построения графа.
- **Анализ по графу знаний** — семантическое обнаружение прямых конфликтов и конфликтов перекрытия иерархий состояний.

## Поддерживаемые шаблоны EARS

| Тип | Шаблон |
|-----|--------|
| Ubiquitous | `The <system> shall <response>` |
| Event-Driven | `When <trigger> the <system> shall <response>` |
| State-Driven | `While <state> the <system> shall <response>` |
| Optional Feature | `Where <feature> the <system> shall <response>` |
| Unwanted Behavior | `If <trigger> then the <system> shall <response>` |

## Обнаруживаемые конфликты

- **UBIQUITOUS CONFLICT** — одна система одновременно должна и не должна выполнять одно и то же действие.
- **STATE-DRIVEN CONFLICT** — одна система в одном состоянии одновременно должна и не должна выполнять действие.
- **STATE CONFLICT** — состояние одновременно разрешает и запрещает активность в графе знаний.
- **STATE OVERLAP CONFLICT** — два состояния с пересекающимися иерархиями дают противоположные предписания для одной активности.

## Структура проекта

```
graduate_work/
├── main.py                      # Точка входа, оркестрация пайплайна
├── models.py                    # Модели данных (Requirement, ReqType)
├── parser.py                    # NLP-парсинг, классификация, извлечение сущностей
├── knowledge_graph.py           # Построение RDF-графа и поиск конфликтов
├── rules.py                     # Проверки по правилам
├── data/
│   ├── action_normalization.json  # Таблица нормализации действий и объектов
│   └── base_ontology.ttl          # Базовая онтология (OWL/Turtle)
├── reqs.txt                     # Пример набора требований
└── requirements.txt             # Зависимости Python
```

## Установка

**Требования:** Python 3.11.1

```bash
pip install -r requirements.txt
```

Если модель spaCy не установлена автоматически:

```bash
python -m spacy download en_core_web_sm
```

## Использование

```bash
# Анализ файла по умолчанию (reqs.txt)
python main.py

# Анализ произвольного файла
python main.py path/to/requirements.txt
```

### Формат входного файла

Каждое требование начинается со строки-заголовка (номер + точка), за которой следует текст:

```
1. Название требования
The System shall activate the heater.

2. Другое требование
While the engine is running, the System shall enable autopilot.
```

### Пример вывода

```
Загрузка требований из файла: reqs.txt
Загружено требований: 39

--- Проверка по правилам ---
[UBIQUITOUS CONFLICT] Представленные требования противоречат:
    REQ-28 - The System shall activate the heater.
    REQ-29 - The System shall deactivate the heater.

--- Построение графа знаний ---
  Добавлено триплетов: 312

--- Анализ на основе графа знаний ---
[STATE CONFLICT] Состояние engine_is_running одновременно разрешает и запрещает действия 'enable' над 'autopilot'.
    Затронутые требования:
    REQ-30 - While the engine is running, the System shall enable autopilot.
    REQ-31 - While the engine is running, the System shouldn't enable autopilot.
```

## Нормализация действий

Файл `data/action_normalization.json` задаёт каноническое представление синонимичных глаголов. Например, `disable`, `deactivate`, `block`, `forbid` приводятся к своим каноническим формам с флагом `negative: true`, что позволяет сравнивать требования вне зависимости от конкретного глагола.

```json
{
  "disable": { "canonical": "enable", "negative": true },
  "deactivate": { "canonical": "activate", "negative": true }
}
```

## Зависимости

| Библиотека | Назначение |
|-----------|-----------|
| spaCy | NLP-анализ: токенизация, POS-теггинг, dependency parsing |
| en_core_web_sm | Языковая модель spaCy (английский) |
| rdflib | Построение и запросы к RDF-графу знаний |
| pydantic | Валидация данных |
