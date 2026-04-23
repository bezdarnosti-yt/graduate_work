"""Общие модели данных и перечисления для анализатора требований."""


from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class ReqType(Enum):
    """Тип требования согласно шаблонам EARS."""

    UBIQUITOUS = 1        # The <system> shall <response>
    EVENT_DRIVEN = 2      # When <trigger> the <system> shall <response>
    STATE_DRIVEN = 3      # While <state> the <system> shall <response>
    OPTIONAL_FEATURE = 4  # Where <feature> the <system> shall <response>
    UNWANTED_BEHAVIOR = 5 # If <trigger> then the <system> shall <response>


class ReqElementType(Enum):
    """Типы элементов, извлекаемых из требования."""

    SYSTEM = 1
    RESPONSE = 2
    EVENT = 3
    STATE = 4
    FUNCTION = 5
    KEYWORD = 6


@dataclass
class Requirement:
    """Представление одного функционального требования."""

    header: str
    raw_text: str
    id: Optional[str] = None            # идентификатор из исходного файла
    req_type: Optional[ReqType] = None
    system: Optional[str] = None
    response: Optional[str] = None
    condition: Optional[str] = None     # объединяет event/state/feature/trigger

    # Нормализованные поля (заполняются парсером)
    canonical_action: Optional[str] = None
    canonical_object: Optional[str] = None
    is_negative: bool = False
    
    tokens: Optional[List] = None       # spaCy Doc для дальнейшего использования
    