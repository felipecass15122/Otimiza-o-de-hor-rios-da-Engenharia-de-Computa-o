"""Formulação de viabilidade do problema de horários em Pyomo."""

from __future__ import annotations

from collections import defaultdict
from functools import partial
from itertools import combinations
from typing import Any

import pyomo.environ as pyo

from horarios_ec.data_loader import DIAS_VALIDOS, HORARIOS_VALIDOS
from utils import restricoes_fracas
from utils.restricoes import regra_h1, regra_h2, regra_h3, regra_h4, regra_h5


def criar_modelo_otimizacao(
    dados_carregados: dict[str, Any],
    peso_s1: float = 1.0,
    peso_s3: float = 1.0,
) -> pyo.ConcreteModel:
    """Constrói o modelo PLIM com as restrições fortes H1 a H5, S1 e S3.

    S1 minimiza os horários vazios entre a primeira e a última aula de cada
    período em um mesmo dia. S3 minimiza o desvio da carga diária de cada
    período em relação à sua média semanal.
    """
    aulas = dados_carregados["aulas"]
    dominios_validos = dados_carregados["dominios_validos"]
    if not aulas:
        raise ValueError("Não é possível criar modelo sem aulas.")
    if not dominios_validos:
        raise ValueError("Não é possível criar modelo sem domínio de decisão.")
    if isinstance(peso_s1, bool) or peso_s1 < 0:
        raise ValueError("O peso de S1 deve ser um número não negativo.")
    if isinstance(peso_s3, bool) or peso_s3 < 0:
        raise ValueError("O peso de S3 deve ser um número não negativo.")

    variaveis_por_aula: dict[str, list[tuple[str, str, str, str]]] = defaultdict(list)
    variaveis_por_aula_horario: dict[
        tuple[str, str, str], list[tuple[str, str, str, str]]
    ] = defaultdict(list)
    variaveis_por_sala_horario: dict[tuple[str, str, str], list[tuple[str, str, str, str]]] = defaultdict(list)
    variaveis_por_professor_horario: dict[tuple[str, str, str], list[tuple[str, str, str, str]]] = defaultdict(list)
    variaveis_por_periodo_horario: dict[
        tuple[str, str, str], list[tuple[str, str, str, str]]
    ] = defaultdict(list)
    horarios_por_aula: dict[str, set[tuple[str, str]]] = defaultdict(set)

    for chave in dominios_validos:
        aula_id, dia, horario, sala = chave
        variaveis_por_aula[aula_id].append(chave)
        variaveis_por_aula_horario[(aula_id, dia, horario)].append(chave)
        variaveis_por_sala_horario[(sala, dia, horario)].append(chave)
        variaveis_por_professor_horario[(aulas[aula_id]["professor"], dia, horario)].append(chave)
        variaveis_por_periodo_horario[(aulas[aula_id]["periodo"], dia, horario)].append(chave)
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
    model.PESO_S1 = pyo.Param(initialize=peso_s1, within=pyo.NonNegativeReals, mutable=True)
    model.PESO_S3 = pyo.Param(initialize=peso_s3, within=pyo.NonNegativeReals, mutable=True)


    model.H1_CargaHoraria = pyo.Constraint(
        model.AULAS,
        rule=partial(
            regra_h1,
            variaveis_por_aula=variaveis_por_aula,
            aulas=aulas,
        ),
    )

    model.H2_INDICE = pyo.Set(
        dimen=3,
        initialize=tuple(sorted(variaveis_por_aula_horario)),
    )
    model.H2_AlocacaoExclusivaSala = pyo.Constraint(
        model.H2_INDICE,
        rule=partial(
            regra_h2,
            variaveis_por_aula_horario=variaveis_por_aula_horario,
        ),
    )

    model.H3_INDICE = pyo.Set(dimen=3, initialize=tuple(sorted(variaveis_por_sala_horario)))

    model.H3_NaoSobreposicaoSala = pyo.Constraint(
        model.H3_INDICE,
        rule=partial(
            regra_h3,
            variaveis_por_sala_horario=variaveis_por_sala_horario,
        ),
    )

    model.H4_INDICE = pyo.Set(dimen=3, initialize=tuple(sorted(variaveis_por_professor_horario)))

    model.H4_ConflitoProfessor = pyo.Constraint(
        model.H4_INDICE,
        rule=partial(
            regra_h4,
            variaveis_por_professor_horario=variaveis_por_professor_horario,
        ),
    )

    model.H5_INDICE = pyo.Set(dimen=4, initialize=tuple(conflitos_h5))

    model.H5_ConflitoPeriodo = pyo.Constraint(
        model.H5_INDICE,
        rule=partial(
            regra_h5,
            variaveis_por_aula=variaveis_por_aula,
        ),
    )

    periodos = tuple(sorted({aula["periodo"] for aula in aulas.values()}))
    model.PERIODOS = pyo.Set(initialize=periodos)
    model.DIAS = pyo.Set(initialize=DIAS_VALIDOS, ordered=True)
    model.HORARIOS = pyo.Set(initialize=HORARIOS_VALIDOS, ordered=True)
    indice_s1 = tuple(
        (periodo, dia, horario)
        for periodo in periodos
        for dia in DIAS_VALIDOS
        for horario in HORARIOS_VALIDOS
    )
    model.S1_INDICE = pyo.Set(dimen=3, initialize=indice_s1)
    model.s1_ocupado = pyo.Var(model.S1_INDICE, domain=pyo.Binary)
    model.s1_tem_antes = pyo.Var(model.S1_INDICE, domain=pyo.Binary)
    model.s1_tem_depois = pyo.Var(model.S1_INDICE, domain=pyo.Binary)
    model.s1_janela = pyo.Var(model.S1_INDICE, domain=pyo.Binary)

    model.S1_OcupacaoMinima = pyo.Constraint(
        model.S1_INDICE,
        rule=partial(
            restricoes_fracas.regra_s1_ocupacao_minima,
            variaveis_por_periodo_horario=variaveis_por_periodo_horario,
        ),
    )

    model.S1_OcupacaoMaxima = pyo.Constraint(
        model.S1_INDICE,
        rule=partial(
            restricoes_fracas.regra_s1_ocupacao_maxima,
            variaveis_por_periodo_horario=variaveis_por_periodo_horario,
        ),
    )

    primeiro_horario = HORARIOS_VALIDOS[0]
    ultimo_horario = HORARIOS_VALIDOS[-1]
    indice_antes = tuple(
        (periodo, dia, horario)
        for periodo in periodos
        for dia in DIAS_VALIDOS
        for horario in HORARIOS_VALIDOS[1:]
    )
    indice_depois = tuple(
        (periodo, dia, horario)
        for periodo in periodos
        for dia in DIAS_VALIDOS
        for horario in HORARIOS_VALIDOS[:-1]
    )
    model.S1_ANTES_INDICE = pyo.Set(dimen=3, initialize=indice_antes)
    model.S1_DEPOIS_INDICE = pyo.Set(dimen=3, initialize=indice_depois)

    model.S1_AntesInicial = pyo.Constraint(
        model.PERIODOS,
        model.DIAS,
        rule=partial(
            restricoes_fracas.regra_s1_antes_inicial,
            primeiro_horario=primeiro_horario,
        ),
    )
    model.S1_DepoisFinal = pyo.Constraint(
        model.PERIODOS,
        model.DIAS,
        rule=partial(
            restricoes_fracas.regra_s1_depois_final,
            ultimo_horario=ultimo_horario,
        ),
    )

    posicao_horario = {horario: indice for indice, horario in enumerate(HORARIOS_VALIDOS)}
    horario_anterior = {
        horario: HORARIOS_VALIDOS[posicao_horario[horario] - 1]
        for horario in HORARIOS_VALIDOS[1:]
    }
    horario_seguinte = {
        horario: HORARIOS_VALIDOS[posicao_horario[horario] + 1]
        for horario in HORARIOS_VALIDOS[:-1]
    }

    model.S1_AntesMantem = pyo.Constraint(
        model.S1_ANTES_INDICE,
        rule=partial(
            restricoes_fracas.regra_s1_antes_mantem,
            horario_anterior=horario_anterior,
        ),
    )
    model.S1_AntesIncluiAnterior = pyo.Constraint(
        model.S1_ANTES_INDICE,
        rule=partial(
            restricoes_fracas.regra_s1_antes_inclui_anterior,
            horario_anterior=horario_anterior,
        ),
    )
    model.S1_AntesMaximo = pyo.Constraint(
        model.S1_ANTES_INDICE,
        rule=partial(
            restricoes_fracas.regra_s1_antes_maximo,
            horario_anterior=horario_anterior,
        ),
    )

    model.S1_DepoisMantem = pyo.Constraint(
        model.S1_DEPOIS_INDICE,
        rule=partial(
            restricoes_fracas.regra_s1_depois_mantem,
            horario_seguinte=horario_seguinte,
        ),
    )
    model.S1_DepoisIncluiSeguinte = pyo.Constraint(
        model.S1_DEPOIS_INDICE,
        rule=partial(
            restricoes_fracas.regra_s1_depois_inclui_seguinte,
            horario_seguinte=horario_seguinte,
        ),
    )
    model.S1_DepoisMaximo = pyo.Constraint(
        model.S1_DEPOIS_INDICE,
        rule=partial(
            restricoes_fracas.regra_s1_depois_maximo,
            horario_seguinte=horario_seguinte,
        ),
    )

    model.S1_JanelaMinima = pyo.Constraint(
        model.S1_INDICE,
        rule=restricoes_fracas.regra_s1_janela_minima,
    )
    model.S1_JanelaLimiteAntes = pyo.Constraint(
        model.S1_INDICE,
        rule=restricoes_fracas.regra_s1_janela_limite_antes,
    )
    model.S1_JanelaLimiteDepois = pyo.Constraint(
        model.S1_INDICE,
        rule=restricoes_fracas.regra_s1_janela_limite_depois,
    )
    model.S1_JanelaSomenteVazia = pyo.Constraint(
        model.S1_INDICE,
        rule=restricoes_fracas.regra_s1_janela_somente_vazia,
    )

    model.s3_aulas_dia = pyo.Expression(
        model.PERIODOS,
        model.DIAS,
        rule=partial(
            restricoes_fracas.expressao_s3_aulas_dia,
            horarios=HORARIOS_VALIDOS,
        ),
    )
    model.s3_media_semanal = pyo.Expression(
        model.PERIODOS,
        rule=partial(
            restricoes_fracas.expressao_s3_media_semanal,
            dias=DIAS_VALIDOS,
        ),
    )
    model.s3_desvio = pyo.Var(
        model.PERIODOS,
        model.DIAS,
        domain=pyo.NonNegativeReals,
    )
    model.S3_DesvioAcima = pyo.Constraint(
        model.PERIODOS,
        model.DIAS,
        rule=restricoes_fracas.regra_s3_desvio_acima,
    )
    model.S3_DesvioAbaixo = pyo.Constraint(
        model.PERIODOS,
        model.DIAS,
        rule=restricoes_fracas.regra_s3_desvio_abaixo,
    )

    model.obj = pyo.Objective(
        expr=(
            model.PESO_S1
            * sum(model.s1_janela[indice] for indice in model.S1_INDICE)
            + model.PESO_S3
            * sum(
                model.s3_desvio[periodo, dia]
                for periodo in model.PERIODOS
                for dia in model.DIAS
            )
        ),
        sense=pyo.minimize,
    )
    return model
