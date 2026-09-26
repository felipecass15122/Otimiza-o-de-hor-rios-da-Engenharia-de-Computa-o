"""Regras das restrições fortes do modelo de horários."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pyomo.environ as pyo

ChaveVariavel = tuple[str, str, str]
VariaveisAgrupadas = Mapping[Any, Sequence[ChaveVariavel]]


def regra_h1(
    modelo: pyo.ConcreteModel,
    aula_id: str,
    variaveis_por_aula: VariaveisAgrupadas,
    aulas: Mapping[str, Mapping[str, Any]],
) -> Any:
    """Exige que cada aula cumpra exatamente sua carga horária semanal."""
    return sum(modelo.y[chave] for chave in variaveis_por_aula[aula_id]) == aulas[
        aula_id
    ]["carga"]


def regra_h3(
    modelo: pyo.ConcreteModel,
    tipo: str,
    dia: str,
    horario: str,
    variaveis_por_tipo_horario: VariaveisAgrupadas,
    capacidade_por_tipo_horario: Mapping[tuple[str, str, str], int],
) -> Any:
    """Limita as aulas à quantidade de salas livres do tipo no horário.

    Como toda aula aceita qualquer sala de sua categoria, essa capacidade é
    equivalente às restrições individuais de não sobreposição de cada sala.
    """
    return (
        sum(
            modelo.y[chave]
            for chave in variaveis_por_tipo_horario[(tipo, dia, horario)]
        )
        <= capacidade_por_tipo_horario[(tipo, dia, horario)]
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
            modelo.y[chave]
            for chave in variaveis_por_professor_horario[(professor, dia, horario)]
        )
        <= 1
    )


def regra_h5(
    modelo: pyo.ConcreteModel,
    periodo: str,
    grupo: str,
    dia: str,
    horario: str,
    variaveis_por_conflito_periodo: VariaveisAgrupadas,
) -> Any:
    """Limita a uma aula cada grupo conflitante de um período no horário."""
    return (
        sum(
            modelo.y[chave]
            for chave in variaveis_por_conflito_periodo[
                (periodo, grupo, dia, horario)
            ]
        )
        <= 1
    )
