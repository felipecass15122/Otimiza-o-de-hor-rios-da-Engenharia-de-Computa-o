"""Regras das restrições fortes do modelo de horários."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pyomo.environ as pyo

ChaveVariavel = tuple[str, str, str, str]
VariaveisAgrupadas = Mapping[Any, Sequence[ChaveVariavel]]


def regra_h1(
    modelo: pyo.ConcreteModel,
    aula_id: str,
    variaveis_por_aula: VariaveisAgrupadas,
    aulas: Mapping[str, Mapping[str, Any]],
) -> Any:
    """Exige que cada aula cumpra exatamente sua carga horária semanal."""
    return sum(modelo.x[chave] for chave in variaveis_por_aula[aula_id]) == aulas[
        aula_id
    ]["carga"]


def regra_h2(
    modelo: pyo.ConcreteModel,
    aula_id: str,
    dia: str,
    horario: str,
    variaveis_por_aula_horario: VariaveisAgrupadas,
) -> Any:
    """Limita cada aula a uma única sala física no mesmo horário."""
    return (
        sum(
            modelo.x[chave]
            for chave in variaveis_por_aula_horario[(aula_id, dia, horario)]
        )
        <= 1
    )


def regra_h3(
    modelo: pyo.ConcreteModel,
    sala: str,
    dia: str,
    horario: str,
    variaveis_por_sala_horario: VariaveisAgrupadas,
) -> Any:
    """Impede que uma sala receba mais de uma aula no mesmo horário."""
    return (
        sum(
            modelo.x[chave]
            for chave in variaveis_por_sala_horario[(sala, dia, horario)]
        )
        <= 1
    )


def regra_h4(
    modelo: pyo.ConcreteModel,
    professor: str,
    dia: str,
    horario: str,
    variaveis_por_professor_horario: VariaveisAgrupadas,
) -> Any:
    """Impede que um professor ministre mais de uma aula no mesmo horário."""
    return (
        sum(
            modelo.x[chave]
            for chave in variaveis_por_professor_horario[(professor, dia, horario)]
        )
        <= 1
    )


def regra_h5(
    modelo: pyo.ConcreteModel,
    aula_a: str,
    aula_b: str,
    dia: str,
    horario: str,
    variaveis_por_aula: VariaveisAgrupadas,
) -> Any:
    """Impede a simultaneidade de duas aulas conflitantes do mesmo período."""
    variaveis_a = [
        modelo.x[chave]
        for chave in variaveis_por_aula[aula_a]
        if chave[1] == dia and chave[2] == horario
    ]
    variaveis_b = [
        modelo.x[chave]
        for chave in variaveis_por_aula[aula_b]
        if chave[1] == dia and chave[2] == horario
    ]
    return sum(variaveis_a) + sum(variaveis_b) <= 1
