"""Comando para resolver e imprimir a grade horária."""

from __future__ import annotations

import argparse
from pathlib import Path

import pyomo.environ as pyo

from horarios_ec.data_loader import carregar_dados
from horarios_ec.model_builder import criar_modelo_otimizacao
from horarios_ec.reporting import imprimir_grade_horaria

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
CAMINHO_AULAS = RAIZ_PROJETO / "data" / "raw" / "disciplinas_professores_ec.json"
CAMINHO_SLOTS = RAIZ_PROJETO / "data" / "raw" / "salas_horarios_disponiveis_somente_37_39_labs.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve a grade horária da Engenharia de Computação.")
    parser.add_argument("--solver", default="glpk", help="Solver Pyomo a utilizar (padrão: glpk).")
    argumentos = parser.parse_args()

    dados = carregar_dados(CAMINHO_AULAS, CAMINHO_SLOTS)
    modelo = criar_modelo_otimizacao(dados)
    solver = pyo.SolverFactory(argumentos.solver)

    try:
        disponivel = solver.available(exception_flag=False)
    except Exception:
        disponivel = False
    if not disponivel:
        print(
            f"Solver '{argumentos.solver}' indisponível. Instale/configure-o no PATH "
            "ou informe outro solver compatível, por exemplo: --solver appsi_highs."
        )
        return 1

    resultado = solver.solve(modelo, tee=False)
    if (
        resultado.solver.status != pyo.SolverStatus.ok
        or resultado.solver.termination_condition != pyo.TerminationCondition.optimal
    ):
        print(
            "O modelo não foi resolvido otimamente: "
            f"status={resultado.solver.status}, "
            f"terminação={resultado.solver.termination_condition}."
        )
        return 2

    imprimir_grade_horaria(modelo, dados)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
