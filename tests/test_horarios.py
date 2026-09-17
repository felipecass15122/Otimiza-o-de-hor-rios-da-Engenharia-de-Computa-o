"""Testes dos incrementos 1 e 2: dados e restrições fortes."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

from horarios_ec.data_loader import carregar_dados
from horarios_ec.model_builder import criar_modelo_otimizacao

AULAS_PATH = BASE_DIR / "data" / "raw" / "disciplinas_professores_ec.json"
SLOTS_PATH = BASE_DIR / "data" / "raw" / "salas_horarios_disponiveis_somente_37_39_labs.json"


@pytest.fixture(scope="module")
def dados_reais() -> dict:
    return carregar_dados(AULAS_PATH, SLOTS_PATH)


def test_carregamento_dos_dados_reais(dados_reais: dict) -> None:
    assert len(dados_reais["aulas"]) == 58
    assert sum(aula["carga"] for aula in dados_reais["aulas"].values()) == 158
    assert len(dados_reais["slots_validos"]) == 554
    assert set(dados_reais["salas_por_tipo"]) == {"sala", "lab_info", "lab_ce", "lab_fis"}
    assert len(dados_reais["salas_fisicas"]) == 8


def test_dominio_contem_apenas_slots_livres_e_compativeis(dados_reais: dict) -> None:
    tipos_por_sala = {
        sala: tipo
        for tipo, salas in dados_reais["salas_por_tipo"].items()
        for sala in salas
    }
    assert dados_reais["dominios_validos"]
    for aula_id, dia, horario, sala in dados_reais["dominios_validos"]:
        assert (sala, dia, horario) in dados_reais["slots_validos"]
        assert tipos_por_sala[sala] == dados_reais["aulas"][aula_id]["local_tipo"]


def test_loader_rejeita_carga_invalida_e_slot_duplicado() -> None:
    slots_validos = [{"local": "37", "tipo": "sala", "dia": "Seg", "horario": "M1"}]
    aulas_invalidas = [
        {"disciplina": "X", "professor": "P", "local": "sala", "periodo": "EC1", "aulas": 0}
    ]
    with patch("horarios_ec.data_loader._carregar_lista_json", side_effect=[aulas_invalidas, slots_validos]):
        with pytest.raises(ValueError, match="inteiro positivo"):
            carregar_dados("aulas.json", "slots.json")

    aulas_validas = [
        {"disciplina": "X", "professor": "P", "local": "sala", "periodo": "EC1", "aulas": 1}
    ]
    slots_duplicados = slots_validos * 2
    with patch("horarios_ec.data_loader._carregar_lista_json", side_effect=[aulas_validas, slots_duplicados]):
        with pytest.raises(ValueError, match="slot duplicado"):
            carregar_dados("aulas.json", "slots.json")


def test_modelo_cria_todas_as_restricoes_fortes(dados_reais: dict) -> None:
    modelo = criar_modelo_otimizacao(dados_reais)
    assert len(modelo.H1_CargaHoraria) == len(dados_reais["aulas"])
    assert len(modelo.H3_NaoSobreposicaoSala) > 0
    assert len(modelo.H4_ConflitoProfessor) > 0
    assert len(modelo.H5_ConflitoPeriodo) > 0


def test_h5_permite_subturmas_distintas_e_bloqueia_turma_geral() -> None:
    aulas = {
        "GERAL": {"disciplina": "Teoria", "professor": "P1", "local_tipo": "sala", "periodo": "EC1", "carga": 1, "subturma": None},
        "G1": {"disciplina": "Lab", "professor": "P2", "local_tipo": "sala", "periodo": "EC1", "carga": 1, "subturma": "G1"},
        "G2": {"disciplina": "Lab", "professor": "P3", "local_tipo": "sala", "periodo": "EC1", "carga": 1, "subturma": "G2"},
    }
    dominio = tuple((aula_id, "Seg", "M1", "37") for aula_id in aulas)
    modelo = criar_modelo_otimizacao({"aulas": aulas, "dominios_validos": dominio})

    pares = {frozenset((aula_a, aula_b)) for aula_a, aula_b, _, _ in modelo.H5_INDICE}
    assert frozenset(("GERAL", "G1")) in pares
    assert frozenset(("GERAL", "G2")) in pares
    assert frozenset(("G1", "G2")) not in pares
