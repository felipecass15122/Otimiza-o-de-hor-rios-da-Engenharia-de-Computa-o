"""Leitura, validação e pré-processamento dos dados do problema."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

DIAS_VALIDOS = ("Seg", "Ter", "Qua", "Qui", "Sex")
HORARIOS_VALIDOS = tuple(
    [f"M{indice}" for indice in range(1, 7)]
    + [f"T{indice}" for indice in range(1, 7)]
    + [f"N{indice}" for indice in range(1, 6)]
)


def _carregar_lista_json(caminho: str | Path, nome: str) -> list[dict[str, Any]]:
    """Lê um arquivo JSON cuja raiz deve ser uma lista de objetos."""
    with Path(caminho).open("r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    if not isinstance(dados, list):
        raise ValueError(f"{nome} deve conter uma lista JSON na raiz.")
    if not dados:
        raise ValueError(f"{nome} não pode estar vazio.")
    if not all(isinstance(item, dict) for item in dados):
        raise ValueError(f"{nome} deve conter somente objetos JSON.")
    return dados


def _texto_obrigatorio(item: dict[str, Any], campo: str, contexto: str) -> str:
    valor = item.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{contexto}: campo '{campo}' deve ser um texto não vazio.")
    return valor


def carregar_dados(caminho_aulas: str | Path, caminho_slots: str | Path) -> dict[str, Any]:
    """Carrega, valida e prepara os dados para a modelagem em Pyomo.

    A variável de decisão só poderá existir nos elementos de
    ``dominios_validos``: slots livres cuja sala física tem o tipo de ambiente
    solicitado pela aula. Assim, H2 é garantida pela construção do domínio.
    """
    aulas_raw = _carregar_lista_json(caminho_aulas, "Arquivo de aulas")
    slots_raw = _carregar_lista_json(caminho_slots, "Arquivo de slots")

    aulas: dict[str, dict[str, Any]] = {}
    for indice, item in enumerate(aulas_raw):
        contexto = f"Aula na posição {indice}"
        carga = item.get("aulas")
        if isinstance(carga, bool) or not isinstance(carga, int) or carga <= 0:
            raise ValueError(f"{contexto}: campo 'aulas' deve ser um inteiro positivo.")

        subturma = item.get("subturma")
        if subturma is not None and (not isinstance(subturma, str) or not subturma.strip()):
            raise ValueError(f"{contexto}: 'subturma' deve ser texto não vazio quando informada.")

        identificador = f"AULA_{indice:03d}"
        aulas[identificador] = {
            "disciplina": _texto_obrigatorio(item, "disciplina", contexto),
            "professor": _texto_obrigatorio(item, "professor", contexto),
            "local_tipo": _texto_obrigatorio(item, "local", contexto),
            "periodo": _texto_obrigatorio(item, "periodo", contexto),
            "carga": carga,
            "subturma": subturma,
        }

    salas_por_tipo_mutavel: dict[str, set[str]] = defaultdict(set)
    sala_para_tipo: dict[str, str] = {}
    slots_validos: set[tuple[str, str, str]] = set()
    slots_por_tipo: dict[str, list[tuple[str, str, str]]] = defaultdict(list)

    for indice, item in enumerate(slots_raw):
        contexto = f"Slot na posição {indice}"
        sala = _texto_obrigatorio(item, "local", contexto)
        tipo = _texto_obrigatorio(item, "tipo", contexto)
        dia = _texto_obrigatorio(item, "dia", contexto)
        horario = _texto_obrigatorio(item, "horario", contexto)

        if dia not in DIAS_VALIDOS:
            raise ValueError(f"{contexto}: dia inválido '{dia}'.")
        if horario not in HORARIOS_VALIDOS:
            raise ValueError(f"{contexto}: horário inválido '{horario}'.")
        if sala in sala_para_tipo and sala_para_tipo[sala] != tipo:
            raise ValueError(f"{contexto}: sala '{sala}' possui tipos conflitantes.")

        chave_slot = (sala, dia, horario)
        if chave_slot in slots_validos:
            raise ValueError(f"{contexto}: slot duplicado {chave_slot!r}.")

        sala_para_tipo[sala] = tipo
        salas_por_tipo_mutavel[tipo].add(sala)
        slots_validos.add(chave_slot)
        slots_por_tipo[tipo].append(chave_slot)

    tipos_sem_sala = sorted(
        {aula["local_tipo"] for aula in aulas.values()} - set(salas_por_tipo_mutavel)
    )
    if tipos_sem_sala:
        raise ValueError(
            "Não existem slots para os tipos de ambiente: " + ", ".join(tipos_sem_sala)
        )

    dominios_validos: list[tuple[str, str, str, str]] = []
    for identificador, aula in aulas.items():
        for sala, dia, horario in slots_por_tipo[aula["local_tipo"]]:
            dominios_validos.append((identificador, dia, horario, sala))

    salas_por_tipo = {
        tipo: tuple(sorted(salas)) for tipo, salas in sorted(salas_por_tipo_mutavel.items())
    }
    return {
        "aulas": aulas,
        "salas_fisicas": tuple(sorted(sala_para_tipo)),
        "salas_por_tipo": salas_por_tipo,
        "slots_validos": frozenset(slots_validos),
        "dominios_validos": tuple(dominios_validos),
    }
