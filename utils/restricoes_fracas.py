"""Regras auxiliares das restrições fracas do modelo de horários."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pyomo.environ as pyo

ChaveVariavel = tuple[str, str, str, str]
VariaveisPorPeriodoHorario = Mapping[tuple[str, str, str], Sequence[ChaveVariavel]]


def soma_aulas_periodo(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dia: str,
    horario: str,
    variaveis_por_periodo_horario: VariaveisPorPeriodoHorario,
) -> Any:
    """Soma as decisões associadas a um período em um horário."""
    chaves = variaveis_por_periodo_horario.get((periodo, dia, horario), ())
    return sum(modelo.x[chave] for chave in chaves)


def regra_s1_ocupacao_minima(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dia: str,
    horario: str,
    variaveis_por_periodo_horario: VariaveisPorPeriodoHorario,
) -> Any:
    """Força a ocupação a zero quando não há nenhuma aula selecionada."""
    return modelo.s1_ocupado[periodo, dia, horario] <= soma_aulas_periodo(
        modelo,
        periodo,
        dia,
        horario,
        variaveis_por_periodo_horario,
    )


def regra_s1_ocupacao_maxima(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dia: str,
    horario: str,
    variaveis_por_periodo_horario: VariaveisPorPeriodoHorario,
) -> Any:
    """Ativa a ocupação quando existe ao menos uma aula selecionada."""
    chaves = variaveis_por_periodo_horario.get((periodo, dia, horario), ())
    if not chaves:
        return pyo.Constraint.Skip
    return sum(modelo.x[chave] for chave in chaves) <= len(chaves) * modelo.s1_ocupado[
        periodo, dia, horario
    ]


def regra_s1_antes_inicial(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dia: str,
    primeiro_horario: str,
) -> Any:
    """Inicia sem ocupação anterior no primeiro horário do dia."""
    return modelo.s1_tem_antes[periodo, dia, primeiro_horario] == 0


def regra_s1_depois_final(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dia: str,
    ultimo_horario: str,
) -> Any:
    """Finaliza sem ocupação posterior no último horário do dia."""
    return modelo.s1_tem_depois[periodo, dia, ultimo_horario] == 0


def regra_s1_antes_mantem(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dia: str,
    horario: str,
    horario_anterior: Mapping[str, str],
) -> Any:
    """Propaga para o horário atual a existência de aula antes do anterior."""
    anterior = horario_anterior[horario]
    return modelo.s1_tem_antes[periodo, dia, horario] >= modelo.s1_tem_antes[
        periodo, dia, anterior
    ]


def regra_s1_antes_inclui_anterior(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dia: str,
    horario: str,
    horario_anterior: Mapping[str, str],
) -> Any:
    """Registra como anterior uma aula existente no horário precedente."""
    anterior = horario_anterior[horario]
    return modelo.s1_tem_antes[periodo, dia, horario] >= modelo.s1_ocupado[
        periodo, dia, anterior
    ]


def regra_s1_antes_maximo(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dia: str,
    horario: str,
    horario_anterior: Mapping[str, str],
) -> Any:
    """Evita ativar o indicador anterior sem uma aula que o justifique."""
    anterior = horario_anterior[horario]
    return modelo.s1_tem_antes[periodo, dia, horario] <= (
        modelo.s1_tem_antes[periodo, dia, anterior]
        + modelo.s1_ocupado[periodo, dia, anterior]
    )


def regra_s1_depois_mantem(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dia: str,
    horario: str,
    horario_seguinte: Mapping[str, str],
) -> Any:
    """Propaga para o horário atual a existência de aula após o seguinte."""
    seguinte = horario_seguinte[horario]
    return modelo.s1_tem_depois[periodo, dia, horario] >= modelo.s1_tem_depois[
        periodo, dia, seguinte
    ]


def regra_s1_depois_inclui_seguinte(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dia: str,
    horario: str,
    horario_seguinte: Mapping[str, str],
) -> Any:
    """Registra como posterior uma aula existente no horário seguinte."""
    seguinte = horario_seguinte[horario]
    return modelo.s1_tem_depois[periodo, dia, horario] >= modelo.s1_ocupado[
        periodo, dia, seguinte
    ]


def regra_s1_depois_maximo(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dia: str,
    horario: str,
    horario_seguinte: Mapping[str, str],
) -> Any:
    """Evita ativar o indicador posterior sem uma aula que o justifique."""
    seguinte = horario_seguinte[horario]
    return modelo.s1_tem_depois[periodo, dia, horario] <= (
        modelo.s1_tem_depois[periodo, dia, seguinte]
        + modelo.s1_ocupado[periodo, dia, seguinte]
    )


def regra_s1_janela_minima(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dia: str,
    horario: str,
) -> Any:
    """Marca uma janela quando há aula antes e depois do horário vazio."""
    return modelo.s1_janela[periodo, dia, horario] >= (
        modelo.s1_tem_antes[periodo, dia, horario]
        + modelo.s1_tem_depois[periodo, dia, horario]
        - modelo.s1_ocupado[periodo, dia, horario]
        - 1
    )


def regra_s1_janela_limite_antes(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dia: str,
    horario: str,
) -> Any:
    """Permite marcar janela somente quando existe alguma aula anterior."""
    return modelo.s1_janela[periodo, dia, horario] <= modelo.s1_tem_antes[
        periodo, dia, horario
    ]


def regra_s1_janela_limite_depois(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dia: str,
    horario: str,
) -> Any:
    """Permite marcar janela somente quando existe alguma aula posterior."""
    return modelo.s1_janela[periodo, dia, horario] <= modelo.s1_tem_depois[
        periodo, dia, horario
    ]


def regra_s1_janela_somente_vazia(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dia: str,
    horario: str,
) -> Any:
    """Impede que um horário ocupado seja contabilizado como janela."""
    return modelo.s1_janela[periodo, dia, horario] <= 1 - modelo.s1_ocupado[
        periodo, dia, horario
    ]


def expressao_s3_aulas_dia(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dia: str,
    horarios: Sequence[str],
) -> Any:
    """Conta os horários ocupados por um período em cada dia."""
    return sum(modelo.s1_ocupado[periodo, dia, horario] for horario in horarios)


def expressao_s3_media_semanal(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dias: Sequence[str],
) -> Any:
    """Calcula a média diária de horários ocupados durante a semana."""
    return sum(modelo.s3_aulas_dia[periodo, dia] for dia in dias) / len(dias)


def regra_s3_desvio_acima(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dia: str,
) -> Any:
    """Limita o desvio quando a carga diária fica acima da média semanal."""
    return modelo.s3_desvio[periodo, dia] >= (
        modelo.s3_aulas_dia[periodo, dia] - modelo.s3_media_semanal[periodo]
    )


def regra_s3_desvio_abaixo(
    modelo: pyo.ConcreteModel,
    periodo: str,
    dia: str,
) -> Any:
    """Limita o desvio quando a carga diária fica abaixo da média semanal."""
    return modelo.s3_desvio[periodo, dia] >= (
        modelo.s3_media_semanal[periodo] - modelo.s3_aulas_dia[periodo, dia]
    )
