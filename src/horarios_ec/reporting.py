"""Apresentação textual da grade resultante do modelo."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pyomo.environ as pyo

from horarios_ec.data_loader import DIAS_VALIDOS, HORARIOS_VALIDOS

AlocacoesTabela = Mapping[tuple[str, str], Sequence[str]]


def _resumir_aula(info_aula: dict[str, Any], sala: str | None = None) -> str:
    """Cria o texto compacto exibido em uma célula da grade."""
    subturma = f" ({info_aula['subturma']})" if info_aula["subturma"] else ""
    resumo = f"{info_aula['disciplina']}{subturma} [{info_aula['professor']}]"
    return f"{resumo} — Sala {sala}" if sala is not None else resumo


def _formatar_celula(conteudos: Sequence[str], largura: int) -> str:
    """Combina alocações simultâneas e limita o texto à largura da coluna."""
    texto = " / ".join(sorted(conteudos)) if conteudos else "-"
    if len(texto) > largura:
        texto = texto[: largura - 3] + "..."
    return f"{texto:<{largura}}"


def _imprimir_tabela_semanal(titulo: str, alocacoes: AlocacoesTabela) -> None:
    """Imprime uma tabela semanal com dias nas colunas e horários nas linhas."""
    largura = 30
    separador = "-" * (10 + len(DIAS_VALIDOS) * (largura + 3))
    cabecalho = " | ".join(
        [f"{'Horário':<8}"] + [f"{dia:<{largura}}" for dia in DIAS_VALIDOS]
    )

    print(f"\n{titulo}")
    print(separador)
    print(cabecalho)
    print(separador)
    for horario in HORARIOS_VALIDOS:
        celulas = [
            _formatar_celula(alocacoes.get((dia, horario), ()), largura)
            for dia in DIAS_VALIDOS
        ]
        print(" | ".join([f"{horario:<8}"] + celulas))
    print(separador)


def _obter_alocacoes_ativas(
    modelo: pyo.ConcreteModel,
) -> list[tuple[str, str, str, str]]:
    """Obtém as decisões selecionadas pelo solver no domínio do modelo."""
    alocacoes_canonicas = getattr(modelo, "_alocacoes_salas", None)
    if alocacoes_canonicas is not None:
        return list(alocacoes_canonicas)

    alocacoes = []
    for aula_id, dia, horario, sala in getattr(modelo, "X_DOMINIO", ()):
        valor = pyo.value(modelo.x[aula_id, dia, horario, sala], exception=False)
        if valor is not None and valor > 0.5:
            alocacoes.append((aula_id, dia, horario, sala))
    return alocacoes


def imprimir_grade_horaria(modelo: pyo.ConcreteModel, dados: dict[str, Any]) -> None:
    """Imprime uma grade semanal separada para cada período pedagógico.

    A função pressupõe que ``modelo`` já foi resolvido. Cada célula informa
    disciplina, subturma, professor e sala física da alocação.
    """
    alocacoes_por_periodo: dict[str, dict[tuple[str, str], list[str]]] = {}

    for aula_id, dia, horario, sala in _obter_alocacoes_ativas(modelo):
        info_aula = dados["aulas"][aula_id]
        periodo = info_aula["periodo"]
        grade_periodo = alocacoes_por_periodo.setdefault(periodo, {})
        grade_periodo.setdefault((dia, horario), []).append(
            _resumir_aula(info_aula, sala)
        )

    if not alocacoes_por_periodo:
        print("Nenhuma aula alocada para exibir.")
        return

    for periodo in sorted(alocacoes_por_periodo):
        _imprimir_tabela_semanal(
            f"GRADE HORÁRIA — PERÍODO: {periodo}",
            alocacoes_por_periodo[periodo],
        )


def imprimir_grade_por_sala(
    modelo: pyo.ConcreteModel,
    dados: dict[str, Any],
) -> None:
    """Imprime uma grade semanal separada para cada sala física utilizada."""
    alocacoes_por_sala: dict[str, dict[tuple[str, str], list[str]]] = {}

    for aula_id, dia, horario, sala in _obter_alocacoes_ativas(modelo):
        grade_sala = alocacoes_por_sala.setdefault(sala, {})
        grade_sala.setdefault((dia, horario), []).append(
            _resumir_aula(dados["aulas"][aula_id])
        )

    if not alocacoes_por_sala:
        print("Nenhuma aula alocada para exibir.")
        return

    for sala in sorted(alocacoes_por_sala):
        _imprimir_tabela_semanal(
            f"GRADE HORÁRIA — SALA: {sala}",
            alocacoes_por_sala[sala],
        )
