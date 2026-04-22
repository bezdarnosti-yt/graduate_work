import sys
from parser import load_normalization_table, parse_all_requirements
from rules import run_rule_checks
from knowledge_graph import KnowledgeGraph


# Чтение входных данных
def read_input(input_file):
    load_normalization_table("data/action_normalization.json")
    print(f"Загрузка требований из файла: {input_file}")
    requirements = parse_all_requirements(input_file)
    print(f"Загружено требований: {len(requirements)}")
    
    return requirements


# Анализ требований при помощи правил
def rule_checks(requirements):
    print("\n--- Проверка по правилам ---")

    rule_conflicts = run_rule_checks(requirements)
    if rule_conflicts:
        for conflict in rule_conflicts:
            print(f"  {conflict}")
    else:
        print("  Конфликтов по правилам не обнаружено.")
	
    return rule_conflicts  # В будущем будем централизованно выводить все конфликты


# Построение графа знаний
def build_knowledge_graph(requirements):
    print("\n--- Построение графа знаний ---")

    knowledge_graph = KnowledgeGraph(
        base_ontology_path="data/base_ontology.ttl"
    )
    knowledge_graph.build_from_requirements(requirements)

    print(f"  Добавлено триплетов: {len(knowledge_graph.graph)}")

    # TODO: Здесь будет вызов методов анализа графа (транзитивные конфликты и пр.)

    return knowledge_graph


# Анализ на основе графа знаний
def ontology_checks(knowledge_graph):
    print("\n--- Анализ на основе графа знаний ---")

    kg_conflicts = knowledge_graph.find_conflicts()
    if kg_conflicts:
        for conflict in kg_conflicts:
            print(f"  {conflict}")
    else:
        print("  Конфликтов по графу знаний не обнаружено.")
    
    return kg_conflicts


def main():
    # Чтение входных данных
    input_file = "reqs.txt"
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    requirements = read_input(input_file)
    
    # Анализ требований при помощи правил
    rule_checks(requirements)
    
    # Построение графа знаний
    knowledge_graph = build_knowledge_graph(requirements)

    # Анализ на основе графа знаний
    ontology_checks(knowledge_graph)
    print("\nАнализ завершён.")


if __name__ == "__main__":
    main()
    