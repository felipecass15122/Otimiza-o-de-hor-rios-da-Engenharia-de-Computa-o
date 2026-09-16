import sys
import pytest
import pyomo.environ as pyo
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

from horarios_ec.data_loader import carregar_dados
from horarios_ec.model_builder import criar_modelo_otimizacao


def imprimir_grade_horaria(modelo: pyo.ConcreteModel, dados: dict) -> None:
    """Imprime a grade horária organizada por salas e em blocos duplos (aulas casadas)."""
    if modelo is None:
        return

    # 1. Mapeamento das alocações da solução
    alocacoes = {}  # (sala, dia, horario) -> texto formatado
    salas_com_aulas = set()

    for a, d, h, s in modelo.X_DOMINIO:
        if pyo.value(modelo.x[a, d, h, s]) > 0.5:
            info_aula = dados["aulas"][a]
            disciplina = info_aula["disciplina"]
            subturma = f" ({info_aula['subturma']})" if info_aula["subturma"] else ""
            prof = info_aula["professor"]
            
            alocacoes[(s, d, h)] = f"{disciplina}{subturma}\n[{prof}]"
            salas_com_aulas.add(s)

    dias = ["Seg", "Ter", "Qua", "Qui", "Sex"]

    # 2. Definição dos blocos de aulas casadas em ordem cronológica
    blocos_horarios = [
        ("M1/M2", "M1", "M2"),
        ("M3/M4", "M3", "M4"),
        ("M5/M6", "M5", "M6"),
        ("T1/T2", "T1", "T2"),
        ("T3/T4", "T3", "T4"),
        ("T5/T6", "T5", "T6"),
        ("N1/N2", "N1", "N2"),
        ("N3/N4", "N3", "N4"),
        ("N5",    "N5", "N5"),  # N5 isolado ou pareado
    ]

    # 3. Impressão formatada por Sala
    for sala in sorted(salas_com_aulas):
        print("\n" + "=" * 115)
        print(f"                                   GRADE HORÁRIA - SALA: {sala}")
        print("=" * 115)
        
        # Cabeçalho dos dias
        print(f"{'Bloco':<8} | {'Segunda':<20} | {'Terça':<20} | {'Quarta':<20} | {'Quinta':<20} | {'Sexta':<20}")
        print("-" * 115)

        for nome_bloco, h1, h2 in blocos_horarios:
            linha_textos = []
            
            for dia in dias:
                # Busca aula no primeiro ou segundo horário do bloco casado
                aula_h1 = alocacoes.get((sala, dia, h1))
                aula_h2 = alocacoes.get((sala, dia, h2))
                
                aula_encontrada = aula_h1 or aula_h2
                
                if aula_encontrada:
                    # Remove quebras de linha para caber na célula da tabela
                    texto_limpo = aula_encontrada.replace("\n", " ")
                    if len(texto_limpo) > 19:
                        texto_limpo = texto_limpo[:16] + "..."
                    linha_textos.append(texto_limpo)
                else:
                    linha_textos.append("-")

            # Formata a linha da tabela
            print(
                f"{nome_bloco:<8} | "
                f"{linha_textos[0]:<20} | "
                f"{linha_textos[1]:<20} | "
                f"{linha_textos[2]:<20} | "
                f"{linha_textos[3]:<20} | "
                f"{linha_textos[4]:<20}"
            )
        print("-" * 115)


def test_carregamento_e_otimizacao():
    """Testa o carregamento de dados, construção e resolução do modelo de otimização."""
    base_path = Path(__file__).parent.parent
    caminho_aulas = base_path / "data"/"raw"/"disciplinas_professores_ec.json"
    caminho_slots = (
        base_path / "data"/ "raw"/ "salas_horarios_disponiveis_somente_37_39_labs.json"
    )

    # 1. Carregamento dos dados
    dados = carregar_dados(str(caminho_aulas), str(caminho_slots))
    assert len(dados["aulas"]) > 0, "Nenhuma aula foi carregada."
    assert (
        len(dados["slots_validos"]) > 0
    ), "Nenhum slot válido foi encontrado."

    # 2. Construção do modelo Pyomo
    modelo = criar_modelo_otimizacao(dados)

    # 3. Resolução via GLPK
    solver = pyo.SolverFactory("appsi_highs")
    if not solver.available():
        # Se estiver rodando via pytest, ignora. Se for script direto, avisa no terminal.
        try:
            pytest.skip("Solver GLPK não está disponível no ambiente.")
        except Exception:
            print("\n[ERRO] O solver GLPK não está instalado/configurado no sistema.")
            print("Instale o GLPK no Windows ou utilize outro solver como HiGHS (highspy).")
            return None, None

    # 3. Resolução via Solver (GLPK)
    #solver = pyo.SolverFactory("glpk")

    if not solver.available():
        pytest.skip("Solver GLPK não está disponível no ambiente.")

    resultado = solver.solve(modelo, tee=False)

    # Assertivas de viabilidade
    assert (
        resultado.solver.status == pyo.SolverStatus.ok
    ), f"Status do solver inesperado: {resultado.solver.status}"
    assert (
        resultado.solver.termination_condition
        == pyo.TerminationCondition.optimal
    ), (
        f"Condição de término não ótima:"
        f" {resultado.solver.termination_condition}"
    )

    # Retorna o modelo resolvido e dados para uso no script principal
    return modelo, dados


if __name__ == "__main__":
    # Executa a otimização e em seguida a impressão formatada
    modelo_resolvido, dados_carregados = test_carregamento_e_otimizacao()
    imprimir_grade_horaria(modelo_resolvido, dados_carregados)