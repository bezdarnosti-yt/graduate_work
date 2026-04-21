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
        
        self.graph.add((EX.has_activity, RDF.type, OWL.ObjectProperty))
        self.graph.add((EX.has_activity, RDFS.domain, EX.System))
        self.graph.add((EX.has_activity, RDFS.range, EX.Activity))

        self._subclass_cache = None  # кеш транзитивного замыкания
        self.req_trace = {}  # Трасировка: (cond_uri, action_uri, pred) -> list of (req_id, req_raw_text)

    """Создаёт минимальную онтологию, если файл не предоставлен."""
    def _init_base_ontology(self):
        # Классы
        self.graph.add((EX.System, RDF.type, OWL.Class))
        self.graph.add((EX.Action, RDF.type, OWL.Class))
        self.graph.add((EX.Object, RDF.type, OWL.Class))
        self.graph.add((EX.Activity, RDF.type, OWL.Class))
        self.graph.add((EX.Condition, RDF.type, OWL.Class))
        self.graph.add((EX.Event, RDF.type, OWL.Class))
        self.graph.add((EX.Event, RDFS.subClassOf, EX.Condition))
        self.graph.add((EX.State, RDF.type, OWL.Class))
        self.graph.add((EX.State, RDFS.subClassOf, EX.Condition))
        self.graph.add((EX.Feature, RDF.type, OWL.Class))
        self.graph.add((EX.Feature, RDFS.subClassOf, EX.Condition))
        self.graph.add((EX.Trigger, RDF.type, OWL.Class))
        self.graph.add((EX.Trigger, RDFS.subClassOf, EX.Condition))

        # Свойства для Activity
        self.graph.add((EX.has_action, RDF.type, OWL.ObjectProperty))
        self.graph.add((EX.has_action, RDFS.domain, EX.Activity))
        self.graph.add((EX.has_action, RDFS.range, EX.Action))

        self.graph.add((EX.has_object, RDF.type, OWL.ObjectProperty))
        self.graph.add((EX.has_object, RDFS.domain, EX.Activity))
        self.graph.add((EX.has_object, RDFS.range, EX.Object))

        # Связь системы с активностью
        self.graph.add((EX.has_activity, RDF.type, OWL.ObjectProperty))
        self.graph.add((EX.has_activity, RDFS.domain, EX.System))
        self.graph.add((EX.has_activity, RDFS.range, EX.Activity))

        # Разрешающие/запрещающие свойства ведут к Activity
        self.graph.add((EX.permits, RDF.type, OWL.ObjectProperty))
        self.graph.add((EX.permits, RDFS.domain, EX.Condition))
        self.graph.add((EX.permits, RDFS.range, EX.Activity))

        self.graph.add((EX.forbids, RDF.type, OWL.ObjectProperty))
        self.graph.add((EX.forbids, RDFS.domain, EX.Condition))
        self.graph.add((EX.forbids, RDFS.range, EX.Activity))

        self.graph.add((EX.triggers, RDF.type, OWL.ObjectProperty))
        self.graph.add((EX.triggers, RDFS.domain, EX.Event))
        self.graph.add((EX.triggers, RDFS.range, EX.Activity))

        self.graph.add((EX.enables, RDF.type, OWL.ObjectProperty))
        self.graph.add((EX.enables, RDFS.domain, EX.Feature))
        self.graph.add((EX.enables, RDFS.range, EX.Activity))

        # Иерархические свойства
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

    # ________________ Блок функций по поиску конфликтов в требованиях ________________
    """
    Возвращает список (state, action, object, pred_type)
    для всех состояний (State) с permits/forbids
    """
    def _get_state_activity_pairs(self):
        query = """
        PREFIX ex: <http://example.org/requirements#>
        SELECT ?state ?activity ?action ?object ?type
        WHERE {
            { ?state ex:permits ?activity . BIND("permits" AS ?type) }
            UNION
            { ?state ex:forbids ?activity . BIND("forbids" AS ?type) }
            ?state a ex:State .
            ?activity ex:has_action ?action .
            OPTIONAL { ?activity ex:has_object ?object }
        }
        """

        results = []
        for row in self.graph.query(query):
            state = URIRef(row.state)
            activity = URIRef(row.activity)
            action = URIRef(row.action)
            obj = URIRef(row.object) if row.object else None
            ptype = str(row.type)
            results.append((state, activity, action, obj, ptype))
        return results

    """Группирует по activity (уникальная комбинация действие + объект)."""
    def _group_by_activity(self, pairs):
        groups = {}
        for state, activity, action, obj, ptype in pairs:
            if activity not in groups:
                groups[activity] = {
                    "permits": set(), "forbids": set(),
                    "action": action, "object": obj
                }
            groups[activity][ptype].add(state)

        return groups

    """Поиск прямых конфликтов"""
    def _find_direct_conflicts(self, activity, info):
        conflicts = []
        direct = info["permits"].intersection(info["forbids"])
        for state in direct:
            reqs = []
            for pred in (EX.permits, EX.forbids):
                key = (state, activity, pred)
                for rid, rtext in self.req_trace.get(key, []):
                    reqs.append(f"{rid} - {rtext}")
            reqs_str = "\n\t".join(reqs)
            action_str = self._format_activity(info["action"], info["object"])
            conflicts.append(
                f"[STATE CONFLICT] Состояние {state.split('#')[-1]} одновременно разрешает и запрещает {action_str}.\n"
                f"\tЗатронутые требования:\n\t{reqs_str}"
            )
        return conflicts

    """Поиск конфликтов перекрытия иерархий"""
    def _find_overlap_conflicts(self, activity, info):
        conflicts = []
        for s_perm in info["permits"]:
            for s_forb in info["forbids"]:
                if s_perm == s_forb:
                    continue
                if self._states_overlap(s_perm, s_forb):
                    reqs = []
                    for pred, state in [(EX.permits, s_perm), (EX.forbids, s_forb)]:
                        key = (state, activity, pred)
                        for rid, rtext in self.req_trace.get(key, []):
                            reqs.append(f"{rid} - {rtext}")
                    reqs_str = "\n\t".join(reqs)
                    action_str = self._format_activity(info["action"], info["object"])
                    conflicts.append(
                        f"[STATE OVERLAP CONFLICT] Состояния '{s_perm.split('#')[-1]}' (разрешает) и '{s_forb.split('#')[-1]}' (запрещает) "
                        f"пересекаются по иерархии для {action_str}.\n"
                        f"\tЗатронутые требования:\n\t{reqs_str}"
                    )
        return conflicts

    """Форматирует ключ действия для вывода"""
    def _format_activity(self, action_uri, object_uri):
        action_name = action_uri.split('#')[-1] if action_uri else "?"
        if object_uri:
            obj_name = object_uri.split('#')[-1]
            return f"действия '{action_name}' над '{obj_name}'"
        return f"действия '{action_name}'"
    
    """
    Ищет семантические конфликты на основе графа:
    - Прямые противоречия (одно состояние и разрешает, и запрещает)
    - Перекрытие состояний (два состояния с разными разрешениями для одного действия, иерархии которых пересекаются)
    """
    def find_conflicts(self) -> List[str]:
        if self._subclass_cache is None:
            self._compute_subclass_closure()

        pairs = self._get_state_activity_pairs()
        groups = self._group_by_activity(pairs)

        all_conflicts = []
        for activity, info in groups.items():
            all_conflicts.extend(self._find_direct_conflicts(activity, info))
            all_conflicts.extend(self._find_overlap_conflicts(activity, info))

        return all_conflicts
    # ________________ Конец блока функций по поиску конфликтов в требованиях ________________
    
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

        # Извлечение глагола и объекта с помощью spaCy
        doc = req.tokens  # spaCy Doc уже сохранён в парсере
        action_lemma = None
        object_text = None
        # Ищем корневой глагол (ROOT) или первый глагол
        for token in doc:
            if token.pos_ == "VERB":
                action_lemma = token.lemma_
                for child in token.children:
                    if child.dep_ == "dobj":
                        object_span = doc[child.left_edge.i : child.right_edge.i + 1]
                        object_text = object_span.text.strip()
                        break
                break

        # Если не нашли глагол, fallback на первое слово
        if not action_lemma:
            action_lemma = normalized_response.split()[0]

        action_uri = self.get_or_create_individual(action_lemma, EX.Action)
        object_uri = None
        if object_text:
            object_uri = self.get_or_create_individual(object_text, EX.Object)

        # Создаём Activity и связываем
        # activity_name формируем как комбинацию для уникальности
        activity_name = f"{action_lemma}_{self._normalize_name(object_text)}" if object_text else action_lemma
        activity_uri = self.get_or_create_individual(activity_name, EX.Activity)
        self.graph.add((activity_uri, EX.has_action, action_uri))
        if object_uri:
            self.graph.add((activity_uri, EX.has_object, object_uri))

        # Связь система-activity
        self.graph.add((sys_uri, EX.has_activity, activity_uri))  # нужно добавить свойство has_activity

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
            self.graph.add((cond_uri, pred, activity_uri))

            # Трассировка
            key = (cond_uri, activity_uri, pred)
            if key not in self.req_trace:
                self.req_trace[key] = []
            self.req_trace[key].append((req.id, req.raw_text))

    """Добавляет в граф данные из списка требований."""
    def build_from_requirements(self, requirements: List[Requirement]):
        for req in requirements:
            self.add_requirement(req)