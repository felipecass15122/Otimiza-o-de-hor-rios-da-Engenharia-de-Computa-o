"""Apresentação textual da grade resultante do modelo."""

from __future__ import annotations

from typing import Any

import pyomo.environ as pyo

DIAS = ("Seg", "Ter", "Qua", "Qui", "Sex")
BLOCOS_HORARIOS = (
    ("M1/M2", "M1", "M2"),
    ("M3/M4", "M3", "M4"),
    ("M5/M6", "M5", "M6"),
    ("T1/T2", "T1", "T2"),
    ("T3/T4", "T3", "T4"),
    ("T5/T6", "T5", "T6"),
    ("N1/N2", "N1", "N2"),
    ("N3/N4", "N3", "N4"),
    ("N5", "N5", "N5"),
)


def _resumir_aula(info_aula: dict[str, Any]) -> str:
    subturma = f" ({info_aula['subturma']})" if info_aula["subturma"] else ""
    return f"{info_aula['disciplina']}{subturma} [{info_aula['professor']}]"


def imprimir_grade_horaria(modelo: pyo.ConcreteModel, dados: dict[str, Any]) -> None:
    """Imprime a grade semanal organizada por sala física.

    A função pressupõe que ``modelo`` já foi resolvido. Cada ocorrência
    alocada é exibida no primeiro módulo do bloco correspondente.
    """
    alocacoes: dict[tuple[str, str, str], str] = {}
    salas_com_aulas: set[str] = set()

    for aula_id, dia, horario, sala in modelo.X_DOMINIO:
        valor = pyo.value(modelo.x[aula_id, dia, horario, sala], exception=False)
        if valor is not None and valor > 0.5:
            alocacoes[(sala, dia, horario)] = _resumir_aula(dados["aulas"][aula_id])
            salas_com_aulas.add(sala)

    if not salas_com_aulas:
        print("Nenhuma aula alocada para exibir.")
        return

    largura = 20
    separador = "-" * (10 + 5 * (largura + 3))
    cabecalho = " | ".join([f"{'Bloco':<8}"] + [f"{dia:<{largura}}" for dia in DIAS])

    for sala in sorted(salas_com_aulas):
        print(f"\nGRADE HORÁRIA — SALA: {sala}")
        print(separador)
        print(cabecalho)
        print(separador)

        for nome_bloco, primeiro_horario, segundo_horario in BLOCOS_HORARIOS:
            celulas = []
            for dia in DIAS:
                texto = (
                    alocacoes.get((sala, dia, primeiro_horario))
                    or alocacoes.get((sala, dia, segundo_horario))
                    or "-"
                )
                celulas.append(f"{texto[:largura - 3] + '...' if len(texto) > largura else texto:<{largura}}")
            print(" | ".join([f"{nome_bloco:<8}"] + celulas))
        print(separador)
