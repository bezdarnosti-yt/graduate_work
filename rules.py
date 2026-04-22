# rules.py
"""Модуль анализа требований на основе предопределённых правил."""

from typing import List
from models import Requirement, ReqType

"""
Ищет прямые противоречия среди повсеместных требований:
"The X shall Y" и "The X shall not Y" (или отрицание Y)
"""
def check_ubiquitous_contradiction(requirements: List[Requirement]) -> List[str]:
    conflicts = []
    # Группируем требования по системе
    ub_reqs = [r for r in requirements if r.req_type == ReqType.UBIQUITOUS and r.system]

    sys_map = {}
    for req in ub_reqs:
        sys_key = req.system.lower()
        if sys_key not in sys_map:
            sys_map[sys_key] = []
        sys_map[sys_key].append(req)

    for sys_key, req_list in sys_map.items():
        # Сравниваем попарно
        for i in range(len(req_list)):
            for j in range(i+1, len(req_list)):
                r1 = req_list[i]
                r2 = req_list[j]
                # Используем нормализованные поля из парсера
                act1 = r1.canonical_action
                act2 = r2.canonical_action
                obj1 = r1.canonical_object or ""
                obj2 = r2.canonical_object or ""
                if act1 and act2 and act1 == act2 and obj1 == obj2:
                    if r1.is_negative != r2.is_negative:
                        conflicts.append(
                            f"[UBIQUITOUS CONFLICT] Представленные требования противоречат:\n\t{r1.id} - {r1.raw_text}\n\t{r2.id} - {r2.raw_text}"
                        )
    return conflicts

"""
Ищет конфликты среди State-Driven требований:
- прямое противоречие (shall/shall not при одном состоянии)
- перекрытие состояний (пока заглушка, в будущем анализ через граф знаний)
"""
def check_state_driven_overlap(requirements: List[Requirement]) -> List[str]:
    conflicts = []
    state_reqs = [r for r in requirements 
                  if r.req_type == ReqType.STATE_DRIVEN 
                  and r.system 
                  and r.condition
                  and r.canonical_action]
    
    # Группируем по системе и состоянию
    grouped = {}
    for req in state_reqs:
        key = (
            req.system.lower(),
            req.condition.lower(),
            req.canonical_action,
            req.canonical_object if req.canonical_object else ""
        )
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(req)

    for (sys, state, action, obj), req_list in grouped.items():
        for i in range(len(req_list)):
            for j in range(i+1, len(req_list)):
                r1 = req_list[i]
                r2 = req_list[j]
                if r1.is_negative != r2.is_negative:
                    obj_str = f" над '{obj}'" if obj else ""
                    conflicts.append(
                        f"[STATE-DRIVEN CONFLICT] Для системы '{sys}' в состоянии '{state}' "
                        f"найдены противоречия для действия '{action}'{obj_str}:\n"
                        f"\t{r1.id} - {r1.raw_text}\n"
                        f"\t{r2.id} - {r2.raw_text}"
                    )
    return conflicts

"""
Выполняет все проверки по правилам, собирает сообщения о конфликтах.
"""
def run_rule_checks(requirements: List[Requirement]) -> List[str]:
    all_conflicts = []
    all_conflicts.extend(check_ubiquitous_contradiction(requirements))
    all_conflicts.extend(check_state_driven_overlap(requirements))
    # Добавить вызовы для других типов конфликтов по мере реализации
    return all_conflicts