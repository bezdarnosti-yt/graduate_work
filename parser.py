# parser.py
"""Модуль разбора текстовых требований, классификации и извлечения сущностей."""

import re
import spacy
from typing import List
from models import Requirement, ReqType

# Загружаем модель spaCy (глобально, чтобы не перезагружать для каждого требования)
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # Если модель не установлена, выводим подсказку
    print("Модель spaCy 'en_core_web_sm' не найдена. Установите: python -m spacy download en_core_web_sm")
    raise

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
Извлекает из текста требования. Возвращает кортеж (system, response, condition).
"""
def extract_system_response_condition(text: str, req_type: ReqType) -> tuple:
    text_clean = text.strip()
    system = None
    response = None
    condition = None

    # Универсальный шаблон для выделения "the ... shall ..."
    # Для разных типов нужно аккуратно извлечь условие.
    match req_type:
        case ReqType.UBIQUITOUS:  # The <system> shall <response>
            pattern = r'^[Tt]he\s+(.+?)\s+shall\s+(.+)$'
            match = re.search(pattern, text_clean)
            if match:
                system = match.group(1).strip()
                response = match.group(2).strip()
        case ReqType.EVENT_DRIVEN:  # When <event> the <system> shall <response>
            pattern = r'^[Ww]hen\s+(.+?)\s+the\s+(.+?)\s+shall\s+(.+)$'
            match = re.search(pattern, text_clean)
            if match:
                condition = match.group(1).strip()
                system = match.group(2).strip()
                response = match.group(3).strip()
        case ReqType.STATE_DRIVEN:  # While <state> the <system> shall <response>
            pattern = r'^[Ww]hile\s+(.+?)\s+the\s+(.+?)\s+shall\s+(.+)$'
            match = re.search(pattern, text_clean)
            if match:
                condition = match.group(1).strip()
                system = match.group(2).strip()
                response = match.group(3).strip()
        case ReqType.OPTIONAL_FEATURE:  # Where <feature> the <system> shall <response>
            pattern = r'^[Ww]here\s+(.+?)\s+the\s+(.+?)\s+shall\s+(.+)$'
            match = re.search(pattern, text_clean)
            if match:
                condition = match.group(1).strip()
                system = match.group(2).strip()
                response = match.group(3).strip()
        case ReqType.UNWANTED_BEHAVIOR:  # If <trigger> then the <system> shall <response>
            pattern = r'^[Ii]f\s+(.+?)\s+then\s+the\s+(.+?)\s+shall\s+(.+)$'
            match = re.search(pattern, text_clean)
            if match:
                condition = match.group(1).strip()
                system = match.group(2).strip()
                response = match.group(3).strip()

    # Если не удалось извлечь, возвращаются пустые строки
    return system, response, condition

"""
Полный цикл обработки одного требования: классификация, извлечение сущностей,
создание объекта Requirement с базовым NLP-анализом (токенизация).
"""
def parse_requirement(req: Requirement) -> Requirement:
    req.req_type = classify_requirement_type(req.raw_text)
    system, response, condition = extract_system_response_condition(req.raw_text, req.req_type)
    req.system = system
    req.response = response
    req.condition = condition

    # Добавляем токенизацию через spaCy для будущего использования
    doc = nlp(req.raw_text)
    req.tokens = doc
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