"""Formulação de viabilidade do problema de horários em Pyomo."""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Any
from utils.restricoes import regra_h1, regra_h3, regra_h4, regra_h5
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


    model.H1_CargaHoraria = pyo.Constraint(
        model.AULAS,
        rule=lambda m, aula_id: regra_h1(
            m,
            aula_id=aula_id,
            variaveis_por_aula=variaveis_por_aula,
            aulas=aulas,
        ),
    )

    model.H3_INDICE = pyo.Set(dimen=3, initialize=tuple(sorted(variaveis_por_sala_horario)))

    model.H3_NaoSobreposicaoSala = pyo.Constraint(
        model.H3_INDICE,
        rule=lambda m, sala, dia, horario: regra_h3(
            m,
            sala=sala,
            dia=dia,
            horario=horario,
            variaveis_por_sala_horario=variaveis_por_sala_horario,
        ),
    )

    model.H4_INDICE = pyo.Set(dimen=3, initialize=tuple(sorted(variaveis_por_professor_horario)))

    model.H4_ConflitoProfessor = pyo.Constraint(
        model.H4_INDICE,
        rule=lambda m, professor, dia, horario: regra_h4(
            m,
            professor=professor,
            dia=dia,
            horario=horario,
            variaveis_por_professor_horario=variaveis_por_professor_horario,
        ),
    )

    model.H5_INDICE = pyo.Set(dimen=4, initialize=tuple(conflitos_h5))

    model.H5_ConflitoPeriodo = pyo.Constraint(
        model.H5_INDICE,
        rule=lambda m, aula_a, aula_b, dia, horario: regra_h5(
            m,
            aula_a=aula_a,
            aula_b=aula_b,
            dia=dia,
            horario=horario,
            variaveis_por_aula=variaveis_por_aula,
        ),
    )
    return model
