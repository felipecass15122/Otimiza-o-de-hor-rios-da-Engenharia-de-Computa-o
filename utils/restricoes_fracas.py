"""Regras auxiliares das restrições fracas S1 e S3."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pyomo.environ as pyo

ChaveHorario = tuple[str, str, str]
VariaveisPorGrupoHorario = Mapping[
    tuple[str, str, str, str], Sequence[ChaveHorario]
]


def expressao_ocupacao_grupo(
    modelo: pyo.ConcreteModel,
    periodo: str,
    grupo: str,
    dia: str,
    horario: str,
    variaveis_por_grupo_horario: VariaveisPorGrupoHorario,
) -> Any:
    """Representa a ocupação do grupo pela soma das aulas no horário.

    H5 garante que essa soma seja zero ou um nas soluções inteiras; por isso
    não é necessária uma variável binária de ocupação nem uma ligação Big-M.
    """
    return sum(
        modelo.y[chave]
        for chave in variaveis_por_grupo_horario.get(
            (periodo, grupo, dia, horario), ()
        )
    )


def regra_s1_antes_inicial(
    modelo: pyo.ConcreteModel,
    periodo: str,
    grupo: str,
    dia: str,
    primeiro_horario: str,
) -> Any:
    """Inicia sem ocupação anterior no primeiro horário do dia."""
    return modelo.s1_tem_antes[periodo, grupo, dia, primeiro_horario] == 0


def regra_s1_depois_final(
    modelo: pyo.ConcreteModel,
    periodo: str,
    grupo: str,
    dia: str,
    ultimo_horario: str,
) -> Any:
    """Finaliza sem ocupação posterior no último horário do dia."""
    return modelo.s1_tem_depois[periodo, grupo, dia, ultimo_horario] == 0


def regra_s1_antes_mantem(
    modelo: pyo.ConcreteModel,
    periodo: str,
    grupo: str,
    dia: str,
    horario: str,
    horario_anterior: Mapping[str, str],
) -> Any:
    """Propaga a existência de aula anterior até o horário atual."""
    anterior = horario_anterior[horario]
    return modelo.s1_tem_antes[periodo, grupo, dia, horario] >= modelo.s1_tem_antes[
        periodo, grupo, dia, anterior
    ]


def regra_s1_antes_inclui_anterior(
    modelo: pyo.ConcreteModel,
    periodo: str,
    grupo: str,
    dia: str,
    horario: str,
    horario_anterior: Mapping[str, str],
) -> Any:
    """Registra uma aula existente no horário imediatamente anterior."""
    anterior = horario_anterior[horario]
    return modelo.s1_tem_antes[periodo, grupo, dia, horario] >= modelo.s1_ocupado[
        periodo, grupo, dia, anterior
    ]


def regra_s1_antes_maximo(
    modelo: pyo.ConcreteModel,
    periodo: str,
    grupo: str,
    dia: str,
    horario: str,
    horario_anterior: Mapping[str, str],
) -> Any:
    """Evita ativar o indicador anterior sem uma aula que o justifique."""
    anterior = horario_anterior[horario]
    return modelo.s1_tem_antes[periodo, grupo, dia, horario] <= (
        modelo.s1_tem_antes[periodo, grupo, dia, anterior]
        + modelo.s1_ocupado[periodo, grupo, dia, anterior]
    )


def regra_s1_depois_mantem(
    modelo: pyo.ConcreteModel,
    periodo: str,
    grupo: str,
    dia: str,
    horario: str,
    horario_seguinte: Mapping[str, str],
) -> Any:
    """Propaga a existência de aula posterior até o horário atual."""
    seguinte = horario_seguinte[horario]
    return modelo.s1_tem_depois[periodo, grupo, dia, horario] >= modelo.s1_tem_depois[
        periodo, grupo, dia, seguinte
    ]


def regra_s1_depois_inclui_seguinte(
    modelo: pyo.ConcreteModel,
    periodo: str,
    grupo: str,
    dia: str,
    horario: str,
    horario_seguinte: Mapping[str, str],
) -> Any:
    """Registra uma aula existente no horário imediatamente seguinte."""
    seguinte = horario_seguinte[horario]
    return modelo.s1_tem_depois[periodo, grupo, dia, horario] >= modelo.s1_ocupado[
        periodo, grupo, dia, seguinte
    ]


def regra_s1_depois_maximo(
    modelo: pyo.ConcreteModel,
    periodo: str,
    grupo: str,
    dia: str,
    horario: str,
    horario_seguinte: Mapping[str, str],
) -> Any:
    """Evita ativar o indicador posterior sem uma aula que o justifique."""
    seguinte = horario_seguinte[horario]
    return modelo.s1_tem_depois[periodo, grupo, dia, horario] <= (
        modelo.s1_tem_depois[periodo, grupo, dia, seguinte]
        + modelo.s1_ocupado[periodo, grupo, dia, seguinte]
    )


def regra_s1_janela_minima(
    modelo: pyo.ConcreteModel,
    periodo: str,
    grupo: str,
    dia: str,
    horario: str,
) -> Any:
    """Marca uma janela quando há aula antes e depois do horário vazio."""
    return modelo.s1_janela[periodo, grupo, dia, horario] >= (
        modelo.s1_tem_antes[periodo, grupo, dia, horario]
        + modelo.s1_tem_depois[periodo, grupo, dia, horario]
        - modelo.s1_ocupado[periodo, grupo, dia, horario]
        - 1
    )


def regra_s1_janela_limite_antes(
    modelo: pyo.ConcreteModel,
    periodo: str,
    grupo: str,
    dia: str,
    horario: str,
) -> Any:
    """Permite uma janela somente quando existe alguma aula anterior."""
    return modelo.s1_janela[periodo, grupo, dia, horario] <= modelo.s1_tem_antes[
        periodo, grupo, dia, horario
    ]


def regra_s1_janela_limite_depois(
    modelo: pyo.ConcreteModel,
    periodo: str,
    grupo: str,
    dia: str,
    horario: str,
) -> Any:
    """Permite uma janela somente quando existe alguma aula posterior."""
    return modelo.s1_janela[periodo, grupo, dia, horario] <= modelo.s1_tem_depois[
        periodo, grupo, dia, horario
    ]


def regra_s1_janela_somente_vazia(
    modelo: pyo.ConcreteModel,
    periodo: str,
    grupo: str,
    dia: str,
    horario: str,
) -> Any:
    """Impede que um horário ocupado seja contabilizado como janela."""
    return modelo.s1_janela[periodo, grupo, dia, horario] <= 1 - modelo.s1_ocupado[
        periodo, grupo, dia, horario
    ]


def regra_s3_carga_dia(
    modelo: pyo.ConcreteModel,
    periodo: str,
    grupo: str,
    dia: str,
    horarios: Sequence[str],
) -> Any:
    """Liga a carga diária à soma dos horários ocupados pelo grupo."""
    return modelo.s3_aulas_dia[periodo, grupo, dia] == sum(
        modelo.s1_ocupado[periodo, grupo, dia, horario] for horario in horarios
    )


def regra_s3_desvio_acima(
    modelo: pyo.ConcreteModel,
    periodo: str,
    grupo: str,
    dia: str,
    quantidade_dias: int,
    carga_semanal_por_grupo: Mapping[tuple[str, str], int],
) -> Any:
    """Limita o desvio escalado quando a carga fica acima da média fixa."""
    return modelo.s3_desvio_escalado[periodo, grupo, dia] >= (
        quantidade_dias * modelo.s3_aulas_dia[periodo, grupo, dia]
        - carga_semanal_por_grupo[(periodo, grupo)]
    )


def regra_s3_desvio_abaixo(
    modelo: pyo.ConcreteModel,
    periodo: str,
    grupo: str,
    dia: str,
    quantidade_dias: int,
    carga_semanal_por_grupo: Mapping[tuple[str, str], int],
) -> Any:
    """Limita o desvio escalado quando a carga fica abaixo da média fixa."""
    return modelo.s3_desvio_escalado[periodo, grupo, dia] >= (
        carga_semanal_por_grupo[(periodo, grupo)]
        - quantidade_dias * modelo.s3_aulas_dia[periodo, grupo, dia]
    )
