"""Utilitários para solução inicial e atribuição canônica de salas."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

import pyomo.environ as pyo

from horarios_ec.data_loader import DIAS_VALIDOS, HORARIOS_VALIDOS


def desativar_restricoes(
    modelo: pyo.ConcreteModel,
    prefixos: tuple[str, ...],
) -> tuple[pyo.Constraint, ...]:
    """Desativa restrições pelos prefixos e devolve os componentes afetados."""
    componentes = tuple(
        componente
        for nome, componente in modelo.component_map(pyo.Constraint).items()
        if nome.startswith(prefixos)
    )
    for componente in componentes:
        componente.deactivate()
    return componentes


def desativar_restricoes_fracas(
    modelo: pyo.ConcreteModel,
) -> tuple[pyo.Constraint, ...]:
    """Desativa S1/S3 durante a busca inicial de viabilidade."""
    return desativar_restricoes(modelo, ("S1_", "S3_"))


def reativar_restricoes(componentes: Iterable[pyo.Constraint]) -> None:
    """Reativa componentes desabilitados durante a fase de viabilidade."""
    for componente in componentes:
        componente.activate()


def capturar_horarios(modelo: pyo.ConcreteModel) -> dict[tuple[str, str, str], int]:
    """Copia as decisões binárias de horário para eventual restauração."""
    return {
        chave: int((pyo.value(modelo.y[chave], exception=False) or 0) > 0.5)
        for chave in modelo.Y_DOMINIO
    }


def restaurar_horarios(
    modelo: pyo.ConcreteModel,
    valores: Mapping[tuple[str, str, str], int],
) -> None:
    """Restaura decisões de horário e recalcula todas as auxiliares."""
    for chave, valor in valores.items():
        modelo.y[chave].set_value(valor)
    preencher_variaveis_auxiliares(modelo)


def preencher_variaveis_auxiliares(modelo: pyo.ConcreteModel) -> None:
    """Completa S1/S3 a partir dos horários de uma solução H1--H5."""
    aulas_ativas_por_grupo: dict[tuple[str, str, str, str], int] = defaultdict(int)
    periodo_por_aula = getattr(modelo, "_periodo_por_aula", None)
    grupos_por_aula = getattr(modelo, "_grupos_por_aula", None)
    if periodo_por_aula is None or grupos_por_aula is None:
        raise ValueError("O modelo não contém os mapas internos de grupos por aula.")

    for chave in modelo.Y_DOMINIO:
        valor = pyo.value(modelo.y[chave], exception=False)
        if valor is not None and valor > 0.5:
            aula_id, dia, horario = chave
            for grupo in grupos_por_aula[aula_id]:
                aulas_ativas_por_grupo[
                    (periodo_por_aula[aula_id], grupo, dia, horario)
                ] += 1

    for periodo, grupo in modelo.GRUPOS:
        cargas_dia: dict[str, int] = {}
        for dia in DIAS_VALIDOS:
            ocupacoes = [
                int(aulas_ativas_por_grupo[(periodo, grupo, dia, horario)] > 0)
                for horario in HORARIOS_VALIDOS
            ]
            cargas_dia[dia] = sum(ocupacoes)
            for indice, horario in enumerate(HORARIOS_VALIDOS):
                ocupado = ocupacoes[indice]
                antes = int(any(ocupacoes[:indice]))
                depois = int(any(ocupacoes[indice + 1 :]))
                janela = int(antes and depois and not ocupado)
                modelo.s1_tem_antes[periodo, grupo, dia, horario].set_value(antes)
                modelo.s1_tem_depois[periodo, grupo, dia, horario].set_value(depois)
                modelo.s1_janela[periodo, grupo, dia, horario].set_value(janela)

        carga_semana = int(pyo.value(modelo.s3_carga_semana[periodo, grupo]))
        for dia in DIAS_VALIDOS:
            modelo.s3_aulas_dia[periodo, grupo, dia].set_value(cargas_dia[dia])
            modelo.s3_desvio_escalado[periodo, grupo, dia].set_value(
                abs(len(DIAS_VALIDOS) * cargas_dia[dia] - carga_semana)
            )


def atribuir_salas(
    modelo: pyo.ConcreteModel,
    dados: dict[str, Any],
) -> tuple[tuple[str, str, str, str], ...]:
    """Atribui salas livres em ordem canônica às decisões de horário ativas.

    A capacidade por tipo já foi garantida por H3. Ordenar aulas e salas
    elimina as permutações equivalentes de ambientes físicos.
    """
    aulas = dados["aulas"]
    salas_disponiveis = dados.get("salas_disponiveis_por_tipo_horario")
    if salas_disponiveis is None:
        tipos_por_sala = {
            sala: tipo
            for tipo, salas in dados["salas_por_tipo"].items()
            for sala in salas
        }
        mutavel: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        for sala, dia, horario in dados["slots_validos"]:
            mutavel[(tipos_por_sala[sala], dia, horario)].add(sala)
        salas_disponiveis = {
            chave: tuple(sorted(salas)) for chave, salas in mutavel.items()
        }

    aulas_por_tipo_horario: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for aula_id, dia, horario in modelo.Y_DOMINIO:
        valor = pyo.value(modelo.y[aula_id, dia, horario], exception=False)
        if valor is not None and valor > 0.5:
            aulas_por_tipo_horario[
                (aulas[aula_id]["local_tipo"], dia, horario)
            ].append(aula_id)

    alocacoes: list[tuple[str, str, str, str]] = []
    for chave, aulas_ativas in sorted(aulas_por_tipo_horario.items()):
        salas_livres = salas_disponiveis.get(chave, ())
        if len(aulas_ativas) > len(salas_livres):
            raise ValueError(
                f"Capacidade de salas insuficiente em {chave}: "
                f"{len(aulas_ativas)} aulas para {len(salas_livres)} salas."
            )
        _, dia, horario = chave
        for aula_id, sala in zip(sorted(aulas_ativas), sorted(salas_livres)):
            alocacoes.append((aula_id, dia, horario, sala))

    resultado = tuple(sorted(alocacoes))
    object.__setattr__(modelo, "_alocacoes_salas", resultado)
    return resultado
