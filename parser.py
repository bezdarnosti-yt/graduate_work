# parser.py
"""Модуль разбора текстовых требований, классификации и извлечения сущностей."""

import re
import json
import spacy
from typing import List, Tuple, Optional
from models import Requirement, ReqType

# Загружаем модель spaCy (глобально, чтобы не перезагружать для каждого требования)
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # Если модель не установлена, выводим подсказку
    print("Модель spaCy 'en_core_web_sm' не найдена. Установите: python -m spacy download en_core_web_sm")
    raise

DEBUG = True
_normalization_table = {}

"""Загружает таблицу нормализации действий и объектов из JSON."""
def load_normalization_table(path: str = "data/action_normalization.json"):
    global _normalization_table
    try:
        with open(path, 'r', encoding='utf-8') as f:
            _normalization_table = json.load(f)
    except FileNotFoundError:
        print(f"Предупреждение: Файл нормализации '{path}' не найден. Будет использована пустая таблица.")
        _normalization_table = {}

"""
Приводит действие и объект к каноническому виду, определяет итоговый флаг отрицания.
Возвращает (canonical_action, canonical_object, is_negative).
"""
def normalize_action_object(action_lemma: str, object_text: Optional[str], explicit_negative: bool) -> Tuple[str, Optional[str], bool]:
    entry = _normalization_table.get(action_lemma, {})
    canonical_action = entry.get("canonical", action_lemma)
    negative_from_entry = entry.get("negative", False)
    is_negative = explicit_negative or negative_from_entry

    canonical_object = object_text
    if object_text:
        # 1. Убираем артикль "the" в начале для унификации
        obj_lower = object_text.strip().lower()
        if obj_lower.startswith("the "):
            obj_normalized = object_text[4:].strip()
        else:
            obj_normalized = object_text.strip()

        # 2. Применяем object_mapping, если есть
        if "object_mapping" in entry:
            obj_map = entry["object_mapping"]
            obj_key = obj_normalized.lower()
            for key, value in obj_map.items():
                if key.strip().lower() == obj_key:
                    canonical_object = value
                    break
            else:
                canonical_object = obj_normalized
        else:
            canonical_object = obj_normalized

    return canonical_action, canonical_object, is_negative

"""
Читает файл с требованиями, извлекает заголовок (строка с номером) и текст требования.
Возвращает список объектов Requirement с заполненными header и raw_text.
"""
def load_requirements_from_file(filepath: str) -> List[Requirement]:
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = [line.rstrip('\n') for line in f]

    requirements = []
    current_header = None
    current_text_lines = []

    for line in lines:
        stripped = line.strip()

        # Проверяем, является ли строка заголовком требования (начинается с номера)
        if re.match(r'^\d+\.\s+', stripped):
            if current_header is not None and current_text_lines:
                req = Requirement(header=current_header, raw_text=" ".join(current_text_lines))
                requirements.append(req)
            
            current_header = stripped
            current_text_lines = []
        elif stripped == "":
            continue
        else:
            current_text_lines.append(stripped)

    if current_header is not None and current_text_lines:
        req = Requirement(header=current_header, raw_text=" ".join(current_text_lines))
        requirements.append(req)

    return requirements

"""
Определяет тип требования по первому ключевому слову (шаблон EARS).
Возвращает ReqType.
"""
def classify_requirement_type(text: str) -> ReqType:
    text_lower = text.lower()
    first_word = text_lower.split(maxsplit=1)[0] if text_lower else ""

    match first_word:
        case "the":
            return ReqType.UBIQUITOUS
        case "when":
            return ReqType.EVENT_DRIVEN
        case "while":
            return ReqType.STATE_DRIVEN
        case "where":
            return ReqType.OPTIONAL_FEATURE
        case "if":
            return ReqType.UNWANTED_BEHAVIOR
        case _:
            # Если не подходит ни под один шаблон, по умолчанию считаем повсеместным
            return ReqType.UBIQUITOUS

"""
Извлекает system, response, condition и is_negative из текста требования EARS.
Устойчива к вложенным 'the' и содержит определение отрицания по глаголу.
"""
def extract_system_response_condition(text: str, req_type: ReqType) -> Tuple[Optional[str], Optional[str], Optional[str], bool]:
    text_clean = text.strip()
    system = None
    response = None
    condition = None
    is_negative = False

    # 1. Ищем глагол требования с отрицанием
    req_verb_pattern = r'\b(shall|should|must|will|may|can)(?:\s+not|\s*n\'t)?\b'
    verb_match = re.search(req_verb_pattern, text_clean, re.IGNORECASE)
    if not verb_match:
        return system, response, condition, is_negative

    verb_full = verb_match.group(0)
    if re.search(r'(not|n\'t)', verb_full, re.IGNORECASE):
        is_negative = True

    verb_start = verb_match.start()
    verb_end = verb_match.end()
    response = text_clean[verb_end:].strip()
    left_part = text_clean[:verb_start].strip()

    if req_type == ReqType.UBIQUITOUS:
        the_match = re.search(r'\b[Tt]he\s+', left_part)
        if the_match:
            system = left_part[the_match.end():].strip()
        else:
            system = left_part
    else:
        parts = re.split(r'\s+(?=[Tt]he\s+)', left_part)
        last_the_idx = -1
        for i in range(len(parts)-1, -1, -1):
            if re.match(r'^[Tt]he\s+', parts[i]):
                last_the_idx = i
                break
        if last_the_idx != -1:
            condition = ' '.join(parts[:last_the_idx]).strip()
            system_part = parts[last_the_idx].strip()
            sys_match = re.match(r'^[Tt]he\s+(.+)$', system_part)
            if sys_match:
                system = sys_match.group(1).strip()
            else:
                system = system_part
        else:
            condition = left_part
            system = ""

        # Очистка condition от ведущего ключевого слова
        if condition:
            first_word = condition.split(maxsplit=1)[0].lower()
            if first_word in {'when', 'while', 'where', 'if'}:
                condition = condition[len(first_word):].strip()

    return system, response, condition, is_negative

"""
Полный цикл обработки одного требования: классификация, извлечение сущностей,
создание объекта Requirement с базовым NLP-анализом (токенизация).
"""
def parse_requirement(req: Requirement) -> Requirement:
    req.req_type = classify_requirement_type(req.raw_text)
    system, response, condition, explicit_neg = extract_system_response_condition(req.raw_text, req.req_type)
    req.system = system
    req.response = response
    req.condition = condition

    # NLP и извлечение глагола/объекта
    doc = nlp(req.raw_text)
    req.tokens = doc

    action_lemma = None
    object_text = None
    # Ищем глагол в ответе, если ответ не пуст
    if response:
        resp_doc = nlp(response)
        for token in resp_doc:
            if token.pos_ == "VERB":
                action_lemma = token.lemma_
                for child in token.children:
                    if child.dep_ == "dobj":
                        object_span = resp_doc[child.left_edge.i : child.right_edge.i + 1]
                        object_text = object_span.text.strip()
                        break
                break
        if not action_lemma:
            action_lemma = response.split()[0]
    else:
        action_lemma = "unknown_action"

    # Нормализация с учётом явного отрицания
    can_action, can_obj, is_neg = normalize_action_object(action_lemma, object_text, explicit_neg)
    req.canonical_action = can_action
    req.canonical_object = can_obj
    req.is_negative = is_neg

    return req

"""
Загружает файл, парсит каждое требование, возвращает список Requirement.
"""
def parse_all_requirements(filepath: str) -> List[Requirement]:
    requirements = load_requirements_from_file(filepath)

    for idx, req in enumerate(requirements):
        req = parse_requirement(req)   # дополняет req_type, system, response, condition, tokens
        req.id = f"REQ-{idx+1}"

    return requirements