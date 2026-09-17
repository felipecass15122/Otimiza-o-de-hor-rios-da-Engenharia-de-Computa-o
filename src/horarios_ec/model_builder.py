"""Formulação de viabilidade do problema de horários em Pyomo."""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Any

import pyomo.environ as pyo


def criar_modelo_otimizacao(dados_carregados: dict[str, Any]) -> pyo.ConcreteModel:
    """Constrói o modelo PLIM com as restrições fortes H1 a H5.

    A função objetivo é constante nesta etapa. O objetivo é validar a
    viabilidade antes da inclusão das restrições suaves e de um solver.
    """
    aulas = dados_carregados["aulas"]
    dominios_validos = dados_carregados["dominios_validos"]
    if not aulas:
        raise ValueError("Não é possível criar modelo sem aulas.")
    if not dominios_validos:
        raise ValueError("Não é possível criar modelo sem domínio de decisão.")

    variaveis_por_aula: dict[str, list[tuple[str, str, str, str]]] = defaultdict(list)
    variaveis_por_sala_horario: dict[tuple[str, str, str], list[tuple[str, str, str, str]]] = defaultdict(list)
    variaveis_por_professor_horario: dict[tuple[str, str, str], list[tuple[str, str, str, str]]] = defaultdict(list)
    horarios_por_aula: dict[str, set[tuple[str, str]]] = defaultdict(set)

    for chave in dominios_validos:
        aula_id, dia, horario, sala = chave
        variaveis_por_aula[aula_id].append(chave)
        variaveis_por_sala_horario[(sala, dia, horario)].append(chave)
        variaveis_por_professor_horario[(aulas[aula_id]["professor"], dia, horario)].append(chave)
        horarios_por_aula[aula_id].add((dia, horario))

    aulas_sem_dominio = sorted(set(aulas) - set(variaveis_por_aula))
    if aulas_sem_dominio:
        raise ValueError("Aulas sem slot compatível: " + ", ".join(aulas_sem_dominio))

    conflitos_h5: list[tuple[str, str, str, str]] = []
    for aula_a, aula_b in combinations(aulas, 2):
        dados_a = aulas[aula_a]
        dados_b = aulas[aula_b]
        if dados_a["periodo"] != dados_b["periodo"]:
            continue

        subturma_a = dados_a["subturma"]
        subturma_b = dados_b["subturma"]
        if subturma_a is not None and subturma_b is not None and subturma_a != subturma_b:
            continue

        for dia, horario in sorted(horarios_por_aula[aula_a] & horarios_por_aula[aula_b]):
            conflitos_h5.append((aula_a, aula_b, dia, horario))

    model = pyo.ConcreteModel()
    model.AULAS = pyo.Set(initialize=tuple(aulas))
    model.X_DOMINIO = pyo.Set(dimen=4, initialize=dominios_validos)
    model.x = pyo.Var(model.X_DOMINIO, domain=pyo.Binary)
    model.obj = pyo.Objective(expr=1, sense=pyo.minimize)

    def regra_h1(m: pyo.ConcreteModel, aula_id: str) -> Any:
        return sum(m.x[chave] for chave in variaveis_por_aula[aula_id]) == aulas[aula_id]["carga"]

    model.H1_CargaHoraria = pyo.Constraint(model.AULAS, rule=regra_h1)

    model.H3_INDICE = pyo.Set(dimen=3, initialize=tuple(sorted(variaveis_por_sala_horario)))

    def regra_h3(m: pyo.ConcreteModel, sala: str, dia: str, horario: str) -> Any:
        return sum(m.x[chave] for chave in variaveis_por_sala_horario[(sala, dia, horario)]) <= 1

    model.H3_NaoSobreposicaoSala = pyo.Constraint(model.H3_INDICE, rule=regra_h3)

    model.H4_INDICE = pyo.Set(dimen=3, initialize=tuple(sorted(variaveis_por_professor_horario)))

    def regra_h4(m: pyo.ConcreteModel, professor: str, dia: str, horario: str) -> Any:
        return sum(m.x[chave] for chave in variaveis_por_professor_horario[(professor, dia, horario)]) <= 1

    model.H4_ConflitoProfessor = pyo.Constraint(model.H4_INDICE, rule=regra_h4)

    model.H5_INDICE = pyo.Set(dimen=4, initialize=tuple(conflitos_h5))

    def regra_h5(m: pyo.ConcreteModel, aula_a: str, aula_b: str, dia: str, horario: str) -> Any:
        variaveis_a = [m.x[chave] for chave in variaveis_por_aula[aula_a] if chave[1] == dia and chave[2] == horario]
        variaveis_b = [m.x[chave] for chave in variaveis_por_aula[aula_b] if chave[1] == dia and chave[2] == horario]
        return sum(variaveis_a) + sum(variaveis_b) <= 1

    model.H5_ConflitoPeriodo = pyo.Constraint(model.H5_INDICE, rule=regra_h5)
    return model
