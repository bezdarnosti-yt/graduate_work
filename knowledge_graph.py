# knowledge_graph.py
"""Модуль для построения и анализа графа знаний предметной области с использованием RDFLib."""

import re
from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef
from typing import Dict, List, Set
from models import Requirement, ReqType

# Определяем пространство имён
EX = Namespace("http://example.org/requirements#")

"""
Граф знаний, основанный на RDF. Хранит онтологию и экземпляры, извлечённые из требований.
"""
class KnowledgeGraph:

    def __init__(self, base_ontology_path: str = None):
        self.graph = Graph()
        self.graph.bind("ex", EX)
        if base_ontology_path:
            self.graph.parse(base_ontology_path, format="turtle")
        else:
            self._init_base_ontology()
        
        self.graph.add((EX.has_action, RDF.type, OWL.ObjectProperty))
        self.graph.add((EX.has_action, RDFS.domain, EX.System))
        self.graph.add((EX.has_action, RDFS.range, EX.Action))

        self._subclass_cache = None  # кеш транзитивного замыкания
        self.req_trace = {}  # Трасировка: (cond_uri, action_uri, pred) -> list of (req_id, req_raw_text)


    """Создаёт минимальную онтологию, если файл не предоставлен."""
    def _init_base_ontology(self):
        # Классы
        self.graph.add((EX.System, RDF.type, OWL.Class))
        self.graph.add((EX.Action, RDF.type, OWL.Class))
        self.graph.add((EX.Condition, RDF.type, OWL.Class))
        self.graph.add((EX.Event, RDF.type, OWL.Class))
        self.graph.add((EX.Event, RDFS.subClassOf, EX.Condition))
        self.graph.add((EX.State, RDF.type, OWL.Class))
        self.graph.add((EX.State, RDFS.subClassOf, EX.Condition))
        self.graph.add((EX.Feature, RDF.type, OWL.Class))
        self.graph.add((EX.Feature, RDFS.subClassOf, EX.Condition))
        self.graph.add((EX.Trigger, RDF.type, OWL.Class))
        self.graph.add((EX.Trigger, RDFS.subClassOf, EX.Condition))

        # Свойства
        self.graph.add((EX.permits, RDF.type, OWL.ObjectProperty))
        self.graph.add((EX.permits, RDFS.domain, EX.Condition))
        self.graph.add((EX.permits, RDFS.range, EX.Action))
        self.graph.add((EX.forbids, RDF.type, OWL.ObjectProperty))
        self.graph.add((EX.forbids, RDFS.domain, EX.Condition))
        self.graph.add((EX.forbids, RDFS.range, EX.Action))
        self.graph.add((EX.triggers, RDF.type, OWL.ObjectProperty))
        self.graph.add((EX.triggers, RDFS.domain, EX.Event))
        self.graph.add((EX.triggers, RDFS.range, EX.Action))
        self.graph.add((EX.enables, RDF.type, OWL.ObjectProperty))
        self.graph.add((EX.enables, RDFS.domain, EX.Feature))
        self.graph.add((EX.enables, RDFS.range, EX.Action))
        self.graph.add((EX.part_of, RDF.type, OWL.ObjectProperty))
        self.graph.add((EX.part_of, RDFS.domain, EX.System))
        self.graph.add((EX.part_of, RDFS.range, EX.System))
        self.graph.add((EX.subclass_of, RDF.type, OWL.TransitiveProperty))
        self.graph.add((EX.subclass_of, RDFS.domain, EX.Condition))
        self.graph.add((EX.subclass_of, RDFS.range, EX.Condition))

    """
    Приводит строку к безопасному фрагменту URI
    """
    def _normalize_name(self, name: str) -> str:
        safe = re.sub(r'[^\w\s]', '', name)
        safe = re.sub(r'\s+', '_', safe)
        safe = re.sub(r'_+', '_', safe).strip('_')
        return safe
    
    """
    Вычисляет транзитивное замыкание отношения ex:subclass_of.
    Возвращает словарь: ключ — URI состояния, значение — множество всех подклассов (включая само состояние).
    """
    def _compute_subclass_closure(self) -> Dict[URIRef, Set[URIRef]]:
        closure = {}

        # Получаем все прямые связи subclass_of
        query = """
        PREFIX ex: <http://example.org/requirements#>
        SELECT ?sub ?super
        WHERE {
            ?sub ex:subclass_of ?super .
        }
        """

        # Инициализируем: каждый класс является подклассом самого себя
        for sub, super in self.graph.query(query):
            s = URIRef(sub)
            o = URIRef(super)
            if s not in closure:
                closure[s] = {s}
            if o not in closure:
                closure[o] = {o}
            closure[s].add(o)

        # Также добавляем все состояния, которые есть в графе, но не участвуют в subclass_of
        all_states = set(self.graph.subjects(RDF.type, EX.State))
        for state in all_states:
            if state not in closure:
                closure[state] = {state}

        # Транзитивное замыкание (алгоритм Флойда-Уоршелла упрощённо)
        changed = True
        while changed:
            changed = False
            for sub in list(closure.keys()):
                for super in list(closure[sub]):
                    if super in closure:
                        for super2 in closure[super]:
                            if super2 not in closure[sub]:
                                closure[sub].add(super2)
                                changed = True
        self._subclass_cache = closure
        return closure

    """
    Проверяет, пересекаются ли иерархии двух состояний (т.е. существует ли состояние,
    которое является подклассом обоих).
    """
    def _states_overlap(self, state1: URIRef, state2: URIRef) -> bool:
        if self._subclass_cache is None:
            self._compute_subclass_closure()
        # sub1 = self._subclass_cache.get(state1, {state1})
        # sub2 = self._subclass_cache.get(state2, {state2})
        # return not sub1.isdisjoint(sub2)

        # Ищем общий подкласс: существует ли состояние c, которое является подклассом и state1, и state2
        for c, supers in self._subclass_cache.items():
            if state1 in supers and state2 in supers:
                return True
        return False

    """
    Ищет семантические конфликты на основе графа:
    - Прямые противоречия (одно состояние и разрешает, и запрещает)
    - Перекрытие состояний (два состояния с разными разрешениями для одного действия, иерархии которых пересекаются)
    """
    def find_conflicts(self) -> List[str]:
        conflicts = []
        if self._subclass_cache is None:
            self._compute_subclass_closure()

        # Получаем все пары (состояние, действие) с permits и forbids
        query = """
        PREFIX ex: <http://example.org/requirements#>
        SELECT ?state ?action ?type
        WHERE {
            { ?state ex:permits ?action . BIND("permits" AS ?type) }
            UNION
            { ?state ex:forbids ?action . BIND("forbids" AS ?type) }
            ?state a ex:State .
        }
        """

        # Группируем по действию
        action_map = {}
        for row in self.graph.query(query):
            state = URIRef(row.state)
            action = URIRef(row.action)
            perm_type = str(row.type)
            if action not in action_map:
                action_map[action] = {"permits": set(), "forbids": set()}
            action_map[action][perm_type].add(state)

        for action, state_sets in action_map.items():
            permits_set = state_sets["permits"]
            forbids_set = state_sets["forbids"]

            # 1. Прямые конфликты (одно состояние и там, и там)
            direct = permits_set.intersection(forbids_set)
            for state in direct:
                reqs = []
                for pred in (EX.permits, EX.forbids):
                    key = (state, action, pred)
                    for rid, rtext in self.req_trace.get(key, []):
                        reqs.append(f"{rid} - {rtext}")
                reqs_str = "\n\t".join(reqs)
                conflicts.append(
                    f"[STATE CONFLICT] Состояние {state.split('#')[-1]} одновременно разрешает и запрещает действие {action.split('#')[-1]}.\n"
                    f"\tЗатронутые требования:\n\t{reqs_str}"
                )

            # 2. Конфликты перекрытия (разные состояния, но иерархии пересекаются)
            for s_perm in permits_set:
                for s_forb in forbids_set:
                    if s_perm == s_forb:
                        continue
                    if self._states_overlap(s_perm, s_forb):
                        reqs = []
                        for pred, state in [(EX.permits, s_perm), (EX.forbids, s_forb)]:
                            key = (state, action, pred)
                            for rid, rtext in self.req_trace.get(key, []):
                                reqs.append(f"{rid} - {rtext}")
                        reqs_str = "\n\t".join(reqs)
                        conflicts.append(
                            f"[STATE OVERLAP CONFLICT] Состояния '{s_perm.split('#')[-1]}' (разрешает) и '{s_forb.split('#')[-1]}' (запрещает) "
                            f"пересекаются по иерархии для действия {action.split('#')[-1]}.\n"
                            f"\tЗатронутые требования:\n\t{reqs_str}"
                        )
        return conflicts
    
    """
    Возвращает URI индивида с заданным именем.
    Если индивид ещё не существует, создаёт его и добавляет в граф с указанным классом.
    """
    def get_or_create_individual(self, name: str, class_uri: URIRef) -> URIRef:
        safe_name = self._normalize_name(name)
        if not safe_name:
            safe_name = "unnamed"
        individual = EX[safe_name]

        # Проверяем существование через ASK-запрос
        q = f"ASK {{ <{individual}> ?p ?o }}"
        exists = bool(self.graph.query(q))
        
        if not exists:
            self.graph.add((individual, RDF.type, class_uri))
        return individual

    """
    Добавляет в граф сущности и связи, извлечённые из требования.
    """
    def add_requirement(self, req: Requirement):
        if not req.system or not req.response:
            return  # Ошибка
 
        sys_uri = self.get_or_create_individual(req.system, EX.System)

        # Нормализация действия: убираем отрицание, если есть
        # В будущем перейдёт в отдельную функцию
        raw_response = req.response.strip()
        is_negative = False
        if raw_response.lower().startswith("not "):  # Пока что отрицание определяем только по ключевому слову not
            is_negative = True
            normalized_response = raw_response[4:].strip()
        else:
            normalized_response = raw_response

        # Действие (реакция)
        # Упрощённо: берём только первое слово действия
        # В будущем можно выделять нормализованное действие
        action_name = normalized_response.split()[0]  # if normalized_response else "unknown_action"
        action_uri = self.get_or_create_individual(action_name, EX.Action)
        
        # Связь система-действие
        self.graph.add((sys_uri, EX.has_action, action_uri))

        if req.condition and req.req_type:
            cond_name = req.condition.strip()
            # Определяем класс условия по типу требования
            match req.req_type:
                case ReqType.EVENT_DRIVEN:
                    cond_class = EX.Event
                    pred = EX.triggers
                case ReqType.STATE_DRIVEN:
                    cond_class = EX.State
                    pred = EX.forbids if is_negative else EX.permits
                case ReqType.OPTIONAL_FEATURE:
                    cond_class = EX.Feature
                    pred = EX.enables
                case ReqType.UNWANTED_BEHAVIOR:
                    cond_class = EX.Trigger
                    pred = EX.triggers
                case _:
                    cond_class = EX.Condition
                    pred = EX.permits

            cond_uri = self.get_or_create_individual(cond_name, cond_class)
            self.graph.add((cond_uri, pred, action_uri))

            # Трассировка
            key = (cond_uri, action_uri, pred)
            if key not in self.req_trace:
                self.req_trace[key] = []
            self.req_trace[key].append((req.id, req.raw_text))

    """Добавляет в граф данные из списка требований."""
    def build_from_requirements(self, requirements: List[Requirement]):
        for req in requirements:
            self.add_requirement(req)