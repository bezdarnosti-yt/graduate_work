# rules.py
"""Модуль анализа требований на основе предопределённых правил."""

from typing import List
from models import Requirement, ReqType

"""
Ищет прямые противоречия среди повсеместных требований:
"The X shall Y" и "The X shall not Y" (или отрицание Y).
Возвращает список сообщений о конфликтах.
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
                # Упрощённая проверка на противоречие: одно содержит отрицание, другое нет.
                # Используем ключевые слова "not" или противоположные глаголы (упрощённо)
                resp1 = r1.response.lower() if r1.response else ""
                resp2 = r2.response.lower() if r2.response else ""
                # Если в одном есть "not", а в другом нет при схожем действии
                if ("not" in resp1) != ("not" in resp2):
                    # Для простоты сравниваем текст без "not"
                    action1 = resp1.replace("not", "").strip()
                    action2 = resp2.replace("not", "").strip()
                    if action1 == action2:
                        conflicts.append(
                            f"[UBIQUITOUS CONFLICT] 'Представленные требования противоречат:\n\t{r1.id} - {r1.raw_text}\n\t{r2.id} - {r2.raw_text}"
                        )
    return conflicts

"""
Ищет конфликты среди State-Driven требований:
- прямое противоречие (shall/shall not при одном состоянии)
- перекрытие состояний (пока заглушка, в будущем анализ через граф знаний)
Пока реализуем только прямые противоречия для одинаковых состояний.
"""
def check_state_driven_overlap(requirements: List[Requirement]) -> List[str]:
    conflicts = []
    state_reqs = [r for r in requirements if r.req_type == ReqType.STATE_DRIVEN and r.system and r.condition]
    # Группируем по системе и состоянию
    grouped = {}
    for req in state_reqs:
        key = (req.system.lower(), req.condition.lower())
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(req)

    for (sys, state), req_list in grouped.items():
        for i in range(len(req_list)):
            for j in range(i+1, len(req_list)):
                r1 = req_list[i]
                r2 = req_list[j]
                resp1 = r1.response.lower() if r1.response else ""
                resp2 = r2.response.lower() if r2.response else ""
                if ("not" in resp1) != ("not" in resp2):
                    action1 = resp1.replace("not", "").strip()
                    action2 = resp2.replace("not", "").strip()
                    if action1 == action2:
                        conflicts.append(
                            f"[STATE-DRIVEN CONFLICT] Для системы '{sys}' в состоянии '{state}' найдены противоречия:\n"
                            f"\t{r1.id} - {r1.raw_text}\n"
                            f"\t{r2.id} - {r2.raw_text}"
                        )
    #       Реализовать проверку перекрытия состояний (например, stateA является подмножеством stateB)
    #       Это потребует онтологии состояний и будет сделано в модуле графа знаний.
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