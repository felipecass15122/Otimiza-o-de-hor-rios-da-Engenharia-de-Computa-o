"""Construção do modelo otimizado de horários em Pyomo."""

from __future__ import annotations

from collections import defaultdict
from functools import partial
from typing import Any

import pyomo.environ as pyo

from horarios_ec.data_loader import DIAS_VALIDOS, HORARIOS_VALIDOS
from horarios_ec.exceptions import ErroConstrucaoModelo
from utils import restricoes_fracas
from utils.restricoes import regra_h1, regra_h3, regra_h4, regra_h5

GRUPO_SEM_SUBTURMA = "__SEM_SUBTURMA__"


def _criar_modelo_otimizacao(
    dados_carregados: dict[str, Any],
    peso_s1: float = 1.0,
    peso_s3: float = 1.0,
) -> pyo.ConcreteModel:
    """Constrói o PLIM de horários com atribuição posterior das salas.

    A decisão binária ``y[aula, dia, horario]`` define somente o horário. A
    quantidade de salas livres de cada categoria é imposta por H3; depois da
    solução, as salas físicas são atribuídas canonicamente. Essa decomposição
    é exata porque toda aula aceita qualquer sala disponível de sua categoria.

    S1 minimiza horários vazios entre a primeira e a última aula do dia. S3
    minimiza o desvio absoluto da carga diária em relação à média semanal.
    """
    aulas = dados_carregados["aulas"]
    dominios_salas = dados_carregados["dominios_validos"]
    if not aulas:
        raise ValueError("Não é possível criar modelo sem aulas.")
    if not dominios_salas:
        raise ValueError("Não é possível criar modelo sem domínio de decisão.")
    if isinstance(peso_s1, bool) or peso_s1 < 0:
        raise ValueError("O peso de S1 deve ser um número não negativo.")
    if isinstance(peso_s3, bool) or peso_s3 < 0:
        raise ValueError("O peso de S3 deve ser um número não negativo.")

    dominio_horarios = tuple(
        dados_carregados.get("dominio_horarios")
        or sorted({(aula_id, dia, horario) for aula_id, dia, horario, _ in dominios_salas})
    )
    periodos = tuple(sorted({aula["periodo"] for aula in aulas.values()}))

    subturmas_por_periodo: dict[str, set[str]] = defaultdict(set)
    for aula in aulas.values():
        if aula["subturma"] is not None:
            subturmas_por_periodo[aula["periodo"]].add(aula["subturma"])
    grupos_conflito_por_periodo = {
        periodo: tuple(sorted(subturmas_por_periodo[periodo]))
        or (GRUPO_SEM_SUBTURMA,)
        for periodo in periodos
    }
    grupos_modelo = tuple(
        (periodo, grupo)
        for periodo in periodos
        for grupo in grupos_conflito_por_periodo[periodo]
    )
    grupos_por_aula = {
        aula_id: (
            grupos_conflito_por_periodo[info["periodo"]]
            if info["subturma"] is None
            else (info["subturma"],)
        )
        for aula_id, info in aulas.items()
    }
    carga_semanal_por_grupo = {
        (periodo, grupo): sum(
            info["carga"]
            for aula_id, info in aulas.items()
            if info["periodo"] == periodo and grupo in grupos_por_aula[aula_id]
        )
        for periodo, grupo in grupos_modelo
    }

    salas_por_tipo_horario: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    salas_por_aula_horario: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for aula_id, dia, horario, sala in dominios_salas:
        tipo = aulas[aula_id]["local_tipo"]
        salas_por_tipo_horario[(tipo, dia, horario)].add(sala)
        salas_por_aula_horario[(aula_id, dia, horario)].add(sala)
    for aula_id, dia, horario in dominio_horarios:
        tipo = aulas[aula_id]["local_tipo"]
        if salas_por_aula_horario[(aula_id, dia, horario)] != salas_por_tipo_horario[
            (tipo, dia, horario)
        ]:
            raise ValueError(
                "A decomposição de salas exige que aulas da mesma categoria possam "
                "usar as mesmas salas em cada horário."
            )
    capacidade_por_tipo_horario = {
        chave: len(salas) for chave, salas in salas_por_tipo_horario.items()
    }

    variaveis_por_aula: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    variaveis_por_tipo_horario: dict[
        tuple[str, str, str], list[tuple[str, str, str]]
    ] = defaultdict(list)
    variaveis_por_professor_horario: dict[
        tuple[str, str, str], list[tuple[str, str, str]]
    ] = defaultdict(list)
    variaveis_por_conflito_periodo: dict[
        tuple[str, str, str, str], list[tuple[str, str, str]]
    ] = defaultdict(list)

    for chave in dominio_horarios:
        aula_id, dia, horario = chave
        info_aula = aulas[aula_id]
        periodo = info_aula["periodo"]
        variaveis_por_aula[aula_id].append(chave)
        variaveis_por_tipo_horario[
            (info_aula["local_tipo"], dia, horario)
        ].append(chave)
        variaveis_por_professor_horario[
            (info_aula["professor"], dia, horario)
        ].append(chave)
        for grupo in grupos_por_aula[aula_id]:
            variaveis_por_conflito_periodo[
                (periodo, grupo, dia, horario)
            ].append(chave)

    aulas_sem_dominio = sorted(set(aulas) - set(variaveis_por_aula))
    if aulas_sem_dominio:
        raise ValueError("Aulas sem slot compatível: " + ", ".join(aulas_sem_dominio))

    model = pyo.ConcreteModel()
    object.__setattr__(
        model,
        "_periodo_por_aula",
        {aula_id: info["periodo"] for aula_id, info in aulas.items()},
    )
    object.__setattr__(model, "_grupos_por_aula", grupos_por_aula)
    object.__setattr__(model, "_carga_semanal_por_grupo", carga_semanal_por_grupo)
    model.AULAS = pyo.Set(initialize=tuple(aulas))
    model.Y_DOMINIO = pyo.Set(dimen=3, initialize=dominio_horarios)
    model.y = pyo.Var(model.Y_DOMINIO, domain=pyo.Binary)
    model.PESO_S1 = pyo.Param(
        initialize=peso_s1, within=pyo.NonNegativeReals, mutable=True
    )
    model.PESO_S3 = pyo.Param(
        initialize=peso_s3, within=pyo.NonNegativeReals, mutable=True
    )
    model.ESCALA_OBJETIVO = pyo.Param(
        initialize=len(DIAS_VALIDOS), within=pyo.PositiveIntegers
    )

    model.H1_CargaHoraria = pyo.Constraint(
        model.AULAS,
        rule=partial(
            regra_h1,
            variaveis_por_aula=variaveis_por_aula,
            aulas=aulas,
        ),
    )

    # H2 é estrutural: y é binária e possui uma única entrada por aula/horário.
    object.__setattr__(model, "_h2_estrutural", True)

    model.H3_INDICE = pyo.Set(
        dimen=3,
        initialize=tuple(
            sorted(
                chave
                for chave, variaveis in variaveis_por_tipo_horario.items()
                if len(variaveis) > capacidade_por_tipo_horario[chave]
            )
        ),
    )
    model.H3_NaoSobreposicaoSala = pyo.Constraint(
        model.H3_INDICE,
        rule=partial(
            regra_h3,
            variaveis_por_tipo_horario=variaveis_por_tipo_horario,
            capacidade_por_tipo_horario=capacidade_por_tipo_horario,
        ),
    )

    model.H4_INDICE = pyo.Set(
        dimen=3,
        initialize=tuple(
            sorted(
                chave
                for chave, variaveis in variaveis_por_professor_horario.items()
                if len(variaveis) > 1
            )
        ),
    )
    model.H4_ConflitoProfessor = pyo.Constraint(
        model.H4_INDICE,
        rule=partial(
            regra_h4,
            variaveis_por_professor_horario=variaveis_por_professor_horario,
        ),
    )

    model.H5_INDICE = pyo.Set(
        dimen=4,
        initialize=tuple(
            sorted(
                chave
                for chave, variaveis in variaveis_por_conflito_periodo.items()
                if len(variaveis) > 1
            )
        ),
    )
    model.H5_ConflitoPeriodo = pyo.Constraint(
        model.H5_INDICE,
        rule=partial(
            regra_h5,
            variaveis_por_conflito_periodo=variaveis_por_conflito_periodo,
        ),
    )

    model.PERIODOS = pyo.Set(initialize=periodos)
    model.GRUPOS = pyo.Set(dimen=2, initialize=grupos_modelo)
    model.DIAS = pyo.Set(initialize=DIAS_VALIDOS, ordered=True)
    model.HORARIOS = pyo.Set(initialize=HORARIOS_VALIDOS, ordered=True)
    indice_s1 = tuple(
        (periodo, grupo, dia, horario)
        for periodo, grupo in grupos_modelo
        for dia in DIAS_VALIDOS
        for horario in HORARIOS_VALIDOS
    )
    model.S1_INDICE = pyo.Set(dimen=4, initialize=indice_s1)
    model.s1_ocupado = pyo.Expression(
        model.S1_INDICE,
        rule=partial(
            restricoes_fracas.expressao_ocupacao_grupo,
            variaveis_por_grupo_horario=variaveis_por_conflito_periodo,
        ),
    )
    model.s1_tem_antes = pyo.Var(model.S1_INDICE, domain=pyo.UnitInterval)
    model.s1_tem_depois = pyo.Var(model.S1_INDICE, domain=pyo.UnitInterval)
    model.s1_janela = pyo.Var(model.S1_INDICE, domain=pyo.UnitInterval)

    primeiro_horario = HORARIOS_VALIDOS[0]
    ultimo_horario = HORARIOS_VALIDOS[-1]
    indice_antes = tuple(
        (periodo, grupo, dia, horario)
        for periodo, grupo in grupos_modelo
        for dia in DIAS_VALIDOS
        for horario in HORARIOS_VALIDOS[1:]
    )
    indice_depois = tuple(
        (periodo, grupo, dia, horario)
        for periodo, grupo in grupos_modelo
        for dia in DIAS_VALIDOS
        for horario in HORARIOS_VALIDOS[:-1]
    )
    model.S1_ANTES_INDICE = pyo.Set(dimen=4, initialize=indice_antes)
    model.S1_DEPOIS_INDICE = pyo.Set(dimen=4, initialize=indice_depois)

    model.S1_AntesInicial = pyo.Constraint(
        model.GRUPOS,
        model.DIAS,
        rule=partial(
            restricoes_fracas.regra_s1_antes_inicial,
            primeiro_horario=primeiro_horario,
        ),
    )
    model.S1_DepoisFinal = pyo.Constraint(
        model.GRUPOS,
        model.DIAS,
        rule=partial(
            restricoes_fracas.regra_s1_depois_final,
            ultimo_horario=ultimo_horario,
        ),
    )

    posicao_horario = {
        horario: indice for indice, horario in enumerate(HORARIOS_VALIDOS)
    }
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
        model.S1_INDICE, rule=restricoes_fracas.regra_s1_janela_minima
    )
    model.S1_JanelaLimiteAntes = pyo.Constraint(
        model.S1_INDICE, rule=restricoes_fracas.regra_s1_janela_limite_antes
    )
    model.S1_JanelaLimiteDepois = pyo.Constraint(
        model.S1_INDICE, rule=restricoes_fracas.regra_s1_janela_limite_depois
    )
    model.S1_JanelaSomenteVazia = pyo.Constraint(
        model.S1_INDICE, rule=restricoes_fracas.regra_s1_janela_somente_vazia
    )

    model.s3_aulas_dia = pyo.Var(
        model.GRUPOS,
        model.DIAS,
        domain=pyo.NonNegativeReals,
        bounds=(0, len(HORARIOS_VALIDOS)),
    )
    model.S3_CargaDia = pyo.Constraint(
        model.GRUPOS,
        model.DIAS,
        rule=partial(
            restricoes_fracas.regra_s3_carga_dia,
            horarios=HORARIOS_VALIDOS,
        ),
    )
    model.s3_carga_semana = pyo.Param(
        model.GRUPOS,
        initialize=carga_semanal_por_grupo,
        within=pyo.NonNegativeIntegers,
    )
    model.s3_media_semanal = pyo.Expression(
        model.GRUPOS,
        rule=lambda m, periodo, grupo: m.s3_carga_semana[periodo, grupo]
        / len(DIAS_VALIDOS),
    )
    model.s3_desvio_escalado = pyo.Var(
        model.GRUPOS,
        model.DIAS,
        domain=pyo.NonNegativeReals,
    )
    model.s3_desvio = pyo.Expression(
        model.GRUPOS,
        model.DIAS,
        rule=lambda m, periodo, grupo, dia: m.s3_desvio_escalado[
            periodo, grupo, dia
        ]
        / len(DIAS_VALIDOS),
    )
    model.S3_DesvioAcima = pyo.Constraint(
        model.GRUPOS,
        model.DIAS,
        rule=partial(
            restricoes_fracas.regra_s3_desvio_acima,
            quantidade_dias=len(DIAS_VALIDOS),
            carga_semanal_por_grupo=carga_semanal_por_grupo,
        ),
    )
    model.S3_DesvioAbaixo = pyo.Constraint(
        model.GRUPOS,
        model.DIAS,
        rule=partial(
            restricoes_fracas.regra_s3_desvio_abaixo,
            quantidade_dias=len(DIAS_VALIDOS),
            carga_semanal_por_grupo=carga_semanal_por_grupo,
        ),
    )

    model.obj = pyo.Objective(
        expr=(
            model.ESCALA_OBJETIVO
            * model.PESO_S1
            * sum(model.s1_janela[indice] for indice in model.S1_INDICE)
            + model.PESO_S3
            * sum(
                model.s3_desvio_escalado[periodo, grupo, dia]
                for periodo, grupo in model.GRUPOS
                for dia in model.DIAS
            )
        ),
        sense=pyo.minimize,
    )
    model.obj_normalizado = pyo.Expression(
        expr=model.obj.expr / model.ESCALA_OBJETIVO
    )
    return model


def criar_modelo_otimizacao(
    dados_carregados: dict[str, Any],
    peso_s1: float = 1.0,
    peso_s3: float = 1.0,
) -> pyo.ConcreteModel:
    """Constrói o modelo e contextualiza qualquer falha ocorrida nessa etapa."""
    try:
        return _criar_modelo_otimizacao(
            dados_carregados,
            peso_s1=peso_s1,
            peso_s3=peso_s3,
        )
    except ErroConstrucaoModelo:
        raise
    except Exception as exc:
        raise ErroConstrucaoModelo(
            f"Falha ao validar os parâmetros ou construir o modelo Pyomo: {exc}"
        ) from exc
