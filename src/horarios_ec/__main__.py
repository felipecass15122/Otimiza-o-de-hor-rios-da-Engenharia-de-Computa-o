"""Comando para resolver e imprimir a grade horária."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from math import isfinite
from pathlib import Path
from threading import Event, Thread
from time import perf_counter
from typing import Any

import pyomo.environ as pyo

from horarios_ec.data_loader import carregar_dados
from horarios_ec.model_builder import criar_modelo_otimizacao
from horarios_ec.reporting import imprimir_grade_horaria
from utils.solucao import (
    atribuir_salas,
    capturar_horarios,
    desativar_restricoes,
    desativar_restricoes_fracas,
    preencher_variaveis_auxiliares,
    reativar_restricoes,
    restaurar_horarios,
)

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
CAMINHO_AULAS = RAIZ_PROJETO / "data" / "raw" / "disciplinas_professores_ec.json"
CAMINHO_SLOTS = RAIZ_PROJETO / "data" / "raw" / "salas_horarios_disponiveis_somente_37_39_labs.json"
LOGGER = logging.getLogger("horarios_ec")


def _criar_parser() -> argparse.ArgumentParser:
    """Cria o parser dos argumentos da execução pela linha de comando."""
    parser = argparse.ArgumentParser(description="Resolve a grade horária da Engenharia de Computação.")
    parser.add_argument("--solver", default="glpk", help="Solver Pyomo a utilizar (padrão: glpk).")
    parser.add_argument(
        "--solver-tee",
        action="store_true",
        help="Exibe também o log nativo produzido pelo solver.",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
        help="Nível dos logs da aplicação (padrão: INFO).",
    )
    parser.add_argument(
        "--log-interval",
        type=float,
        default=30.0,
        help="Intervalo em segundos do aviso enquanto o solver executa (padrão: 30).",
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        default=None,
        help="Limite total aproximado das duas fases do solver, em segundos.",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=0,
        help="Threads do HiGHS; zero mantém a seleção automática (padrão: 0).",
    )
    parser.add_argument(
        "--no-parallel",
        action="store_false",
        dest="parallel",
        help="Desabilita a busca MIP paralela do HiGHS.",
    )
    parser.set_defaults(parallel=True)
    parser.add_argument(
        "--mip-gap",
        type=float,
        default=None,
        help="Gap relativo opcional do MIP, por exemplo 0.01 para 1%%.",
    )
    parser.add_argument(
        "--mip-abs-gap",
        type=float,
        default=None,
        help="Gap absoluto opcional no objetivo escalado.",
    )
    parser.add_argument(
        "--heuristic-effort",
        type=float,
        default=0.2,
        help="Esforço das heurísticas MIP do HiGHS entre 0 e 1 (padrão: 0.2).",
    )
    parser.add_argument(
        "--presolve",
        choices=("on", "off", "choose"),
        default="on",
        help="Configuração do presolve do HiGHS (padrão: on).",
    )
    parser.add_argument(
        "--no-symmetry-detection",
        action="store_false",
        dest="detectar_simetria",
        help="Desabilita a detecção de simetrias do HiGHS.",
    )
    parser.set_defaults(detectar_simetria=True)
    return parser


def _configurar_logging(nivel: str) -> None:
    """Configura logs com horário, nível e mensagem."""
    logging.basicConfig(
        level=getattr(logging, nivel),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("pyomo").setLevel(logging.WARNING)


def _monitorar_solver(parar: Event, inicio: float, intervalo: float) -> None:
    """Emite mensagens periódicas enquanto a chamada bloqueante do solver executa."""
    while not parar.wait(intervalo):
        LOGGER.info(
            "Solver ainda em execução (%.1f segundos decorridos).",
            perf_counter() - inicio,
        )


def _resolver_com_monitoramento(
    solver: Any,
    modelo: pyo.ConcreteModel,
    exibir_log_solver: bool,
    intervalo_log: float,
    warmstart: bool = False,
) -> Any:
    """Executa o solver com um monitor periódico em uma thread auxiliar."""
    parar = Event()
    inicio = perf_counter()
    monitor = Thread(
        target=_monitorar_solver,
        args=(parar, inicio, intervalo_log),
        name="monitor-solver",
        daemon=True,
    )
    monitor.start()
    try:
        opcoes_solve = {
            "tee": exibir_log_solver,
            "load_solutions": False,
        }
        if warmstart:
            opcoes_solve["warmstart"] = True
        return solver.solve(modelo, **opcoes_solve)
    finally:
        parar.set()
        monitor.join(timeout=1)


def _configurar_limite_tempo(solver: Any, nome_solver: str, limite: float) -> None:
    """Aplica o nome de opção de tempo esperado pelos solvers conhecidos."""
    if nome_solver in {"appsi_highs", "highs"}:
        solver.options["time_limit"] = limite
    elif nome_solver == "glpk":
        solver.options["tmlim"] = max(1, int(limite))
    else:
        LOGGER.warning(
            "O limite de tempo não foi aplicado: solver '%s' não possui mapeamento conhecido.",
            nome_solver,
        )


def _configurar_desempenho_solver(
    solver: Any,
    nome_solver: str,
    threads: int,
    paralelo: bool,
    mip_gap: float | None,
    mip_abs_gap: float | None,
    esforco_heuristico: float,
    presolve: str,
    detectar_simetria: bool,
) -> None:
    """Configura paralelismo e tolerância dos solvers que oferecem suporte."""
    if nome_solver not in {"appsi_highs", "highs"}:
        if (
            threads > 0
            or not paralelo
            or mip_gap is not None
            or mip_abs_gap is not None
            or esforco_heuristico != 0.2
            or presolve != "on"
            or not detectar_simetria
        ):
            LOGGER.warning(
                "Threads, paralelismo e MIP gap não foram aplicados ao solver '%s'.",
                nome_solver,
            )
        return

    solver.options["parallel"] = "on" if paralelo else "off"
    if threads > 0:
        solver.options["threads"] = threads
    if mip_gap is not None:
        solver.options["mip_rel_gap"] = mip_gap
    if mip_abs_gap is not None:
        solver.options["mip_abs_gap"] = mip_abs_gap
    solver.options["mip_heuristic_effort"] = esforco_heuristico
    solver.options["presolve"] = presolve
    solver.options["mip_detect_symmetry"] = detectar_simetria

    LOGGER.info(
        "HiGHS configurado: paralelo=%s, threads=%s, mip_gap=%s, "
        "mip_abs_gap=%s, heurísticas=%s, presolve=%s, simetria=%s.",
        paralelo,
        threads if threads > 0 else "automático",
        mip_gap if mip_gap is not None else "padrão do solver",
        mip_abs_gap if mip_abs_gap is not None else "padrão do solver",
        esforco_heuristico,
        presolve,
        detectar_simetria,
    )


def _resultado_possui_solucao(resultado: Any) -> bool:
    """Informa se o resultado contém ao menos uma solução primal finita."""
    terminacao = getattr(getattr(resultado, "solver", None), "termination_condition", None)
    if terminacao in {
        pyo.TerminationCondition.optimal,
        pyo.TerminationCondition.feasible,
        pyo.TerminationCondition.locallyOptimal,
    }:
        return True
    limite_superior = getattr(getattr(resultado, "problem", None), "upper_bound", None)
    try:
        return limite_superior is not None and isfinite(float(limite_superior))
    except (TypeError, ValueError):
        return False


def _suporta_warmstart(solver: Any) -> bool:
    """Consulta o suporte a MIP start sem depender de uma classe de solver."""
    capacidade = getattr(solver, "warm_start_capable", None)
    if not callable(capacidade):
        return False
    try:
        return bool(capacidade())
    except Exception:
        return False


def _executar_fluxo(argumentos: argparse.Namespace) -> int:
    """Executa as etapas do fluxo e converte falhas conhecidas em códigos de saída."""
    inicio_total = perf_counter()
    LOGGER.info("Iniciando otimização dos horários.")
    LOGGER.debug("Arquivo de aulas: %s", CAMINHO_AULAS)
    LOGGER.debug("Arquivo de slots: %s", CAMINHO_SLOTS)

    inicio_etapa = perf_counter()
    try:
        LOGGER.info("Carregando e validando os arquivos de entrada.")
        dados = carregar_dados(CAMINHO_AULAS, CAMINHO_SLOTS)
    except Exception:
        LOGGER.exception("Falha ao carregar ou validar os dados de entrada.")
        return 3
    LOGGER.info(
        "Dados carregados em %.2fs: %d aulas, %d slots, %d combinações aula-sala "
        "e %d decisões aula-horário.",
        perf_counter() - inicio_etapa,
        len(dados["aulas"]),
        len(dados["slots_validos"]),
        len(dados["dominios_validos"]),
        len(dados["dominio_horarios"]),
    )

    inicio_etapa = perf_counter()
    try:
        LOGGER.info("Construindo o modelo Pyomo e suas restrições.")
        modelo = criar_modelo_otimizacao(dados)
    except Exception:
        LOGGER.exception("Falha durante a construção do modelo de otimização.")
        return 4
    quantidade_variaveis = sum(
        1 for _ in modelo.component_data_objects(pyo.Var, active=True)
    )
    quantidade_restricoes = sum(
        1 for _ in modelo.component_data_objects(pyo.Constraint, active=True)
    )
    quantidade_binarias = sum(
        1
        for variavel in modelo.component_data_objects(pyo.Var, active=True)
        if variavel.is_binary()
    )
    LOGGER.info(
        "Modelo construído em %.2fs: %d variáveis (%d binárias) e %d restrições.",
        perf_counter() - inicio_etapa,
        quantidade_variaveis,
        quantidade_binarias,
        quantidade_restricoes,
    )

    try:
        LOGGER.info("Inicializando o solver '%s'.", argumentos.solver)
        solver_viabilidade = pyo.SolverFactory(argumentos.solver)
        disponivel = solver_viabilidade.available(exception_flag=False)
    except Exception:
        LOGGER.exception("Falha ao inicializar ou consultar o solver '%s'.", argumentos.solver)
        return 5
    if not disponivel:
        LOGGER.error(
            "Solver '%s' indisponível. Instale/configure-o no PATH ou use --solver appsi_highs.",
            argumentos.solver,
        )
        return 1

    _configurar_desempenho_solver(
        solver_viabilidade,
        argumentos.solver,
        threads=argumentos.threads,
        paralelo=argumentos.parallel,
        mip_gap=None,
        mip_abs_gap=None,
        esforco_heuristico=argumentos.heuristic_effort,
        presolve=argumentos.presolve,
        detectar_simetria=argumentos.detectar_simetria,
    )

    inicio_solver = perf_counter()
    objetivo_original = modelo.obj.expr
    componentes_fracos = desativar_restricoes_fracas(modelo)
    modelo.obj.set_value(0)
    limite_fase_viabilidade = (
        min(30.0, argumentos.time_limit)
        if argumentos.time_limit is not None
        else 30.0
    )
    _configurar_limite_tempo(
        solver_viabilidade,
        argumentos.solver,
        limite_fase_viabilidade,
    )

    try:
        LOGGER.info(
            "Fase 1/3: buscando uma grade viável somente com H1--H5 "
            "(limite %.1fs).",
            limite_fase_viabilidade,
        )
        resultado_viabilidade = _resolver_com_monitoramento(
            solver_viabilidade,
            modelo,
            exibir_log_solver=argumentos.solver_tee,
            intervalo_log=argumentos.log_interval,
        )
        if not _resultado_possui_solucao(resultado_viabilidade):
            terminacao = resultado_viabilidade.solver.termination_condition
            LOGGER.error(
                "A fase de viabilidade terminou sem grade utilizável: terminação=%s.",
                terminacao,
            )
            return 2
        modelo.solutions.load_from(resultado_viabilidade)
        preencher_variaveis_auxiliares(modelo)
    except Exception:
        LOGGER.exception("Falha durante a fase de viabilidade do solver.")
        return 6
    finally:
        reativar_restricoes(componentes_fracos)
        modelo.obj.set_value(objetivo_original)

    tempo_viabilidade = perf_counter() - inicio_solver
    valor_inicial = pyo.value(modelo.obj_normalizado, exception=False)
    LOGGER.info(
        "Grade inicial viável construída em %.2fs: objetivo normalizado=%s.",
        tempo_viabilidade,
        valor_inicial,
    )

    tempo_restante = None
    if argumentos.time_limit is not None:
        tempo_restante = max(0.0, argumentos.time_limit - tempo_viabilidade)

    melhores_horarios = capturar_horarios(modelo)
    melhor_objetivo = float(valor_inicial)
    limite_melhoria = (
        15.0
        if tempo_restante is None
        else min(15.0, max(3.0, tempo_restante * 0.2))
    )
    if tempo_restante is None or tempo_restante >= 6.0:
        componentes_s1 = desativar_restricoes(modelo, ("S1_",))
        objetivo_completo = modelo.obj.expr
        modelo.obj.set_value(
            modelo.PESO_S3
            * sum(
                modelo.s3_desvio_escalado[periodo, grupo, dia]
                for periodo, grupo in modelo.GRUPOS
                for dia in modelo.DIAS
            )
        )
        encontrou_melhoria = False
        try:
            solver_melhoria = pyo.SolverFactory(argumentos.solver)
            _configurar_limite_tempo(
                solver_melhoria,
                argumentos.solver,
                limite_melhoria,
            )
            _configurar_desempenho_solver(
                solver_melhoria,
                argumentos.solver,
                threads=argumentos.threads,
                paralelo=argumentos.parallel,
                mip_gap=0.01,
                mip_abs_gap=argumentos.mip_abs_gap,
                esforco_heuristico=max(argumentos.heuristic_effort, 0.5),
                presolve=argumentos.presolve,
                detectar_simetria=argumentos.detectar_simetria,
            )
            LOGGER.info(
                "Fase 2/3: melhorando o balanceamento S3 por até %.1fs.",
                limite_melhoria,
            )
            resultado_melhoria = _resolver_com_monitoramento(
                solver_melhoria,
                modelo,
                exibir_log_solver=argumentos.solver_tee,
                intervalo_log=argumentos.log_interval,
                warmstart=_suporta_warmstart(solver_melhoria),
            )
            if _resultado_possui_solucao(resultado_melhoria):
                modelo.solutions.load_from(resultado_melhoria)
                encontrou_melhoria = True
        except Exception:
            LOGGER.exception(
                "A fase intermediária falhou; a grade inicial será preservada."
            )
        finally:
            reativar_restricoes(componentes_s1)
            modelo.obj.set_value(objetivo_completo)

        if encontrou_melhoria:
            preencher_variaveis_auxiliares(modelo)
            objetivo_candidato = float(pyo.value(modelo.obj_normalizado))
            if objetivo_candidato < melhor_objetivo:
                melhor_objetivo = objetivo_candidato
                melhores_horarios = capturar_horarios(modelo)
                LOGGER.info(
                    "Fase intermediária melhorou o objetivo normalizado para %s.",
                    melhor_objetivo,
                )
            else:
                restaurar_horarios(modelo, melhores_horarios)
                LOGGER.info(
                    "Fase intermediária não melhorou o objetivo completo; "
                    "a grade anterior foi restaurada."
                )

        if argumentos.time_limit is not None:
            tempo_restante = max(
                0.0,
                argumentos.time_limit - (perf_counter() - inicio_solver),
            )

    solucao_otima = False
    resultado = None
    if tempo_restante is None or tempo_restante >= 1.0:
        try:
            solver = pyo.SolverFactory(argumentos.solver)
            if tempo_restante is not None:
                _configurar_limite_tempo(
                    solver,
                    argumentos.solver,
                    tempo_restante,
                )
                LOGGER.info(
                    "Tempo restante para otimização completa: %.1fs.",
                    tempo_restante,
                )
            _configurar_desempenho_solver(
                solver,
                argumentos.solver,
                threads=argumentos.threads,
                paralelo=argumentos.parallel,
                mip_gap=argumentos.mip_gap,
                mip_abs_gap=argumentos.mip_abs_gap,
                esforco_heuristico=argumentos.heuristic_effort,
                presolve=argumentos.presolve,
                detectar_simetria=argumentos.detectar_simetria,
            )
            usar_warmstart = _suporta_warmstart(solver)
            LOGGER.info(
                "Fase 3/3: otimizando S1/S3 com solução inicial%s.",
                " via warm start" if usar_warmstart else "",
            )
            resultado = _resolver_com_monitoramento(
                solver,
                modelo,
                exibir_log_solver=argumentos.solver_tee,
                intervalo_log=argumentos.log_interval,
                warmstart=usar_warmstart,
            )
        except Exception:
            LOGGER.exception("Falha durante a otimização completa; usando a grade inicial viável.")
            resultado = None

    if resultado is not None:
        status = resultado.solver.status
        terminacao = resultado.solver.termination_condition
        escala_objetivo = float(pyo.value(modelo.ESCALA_OBJETIVO))
        limite_inferior = getattr(resultado.problem, "lower_bound", None)
        limite_superior = getattr(resultado.problem, "upper_bound", None)
        limite_inferior_normalizado = (
            float(limite_inferior) / escala_objetivo
            if limite_inferior is not None and isfinite(float(limite_inferior))
            else limite_inferior
        )
        limite_superior_normalizado = (
            float(limite_superior) / escala_objetivo
            if limite_superior is not None and isfinite(float(limite_superior))
            else limite_superior
        )
        LOGGER.info(
            "Fase completa finalizada em %.2fs: status=%s, terminação=%s, "
            "limite_inferior=%s, limite_superior=%s.",
            perf_counter() - inicio_solver,
            status,
            terminacao,
            limite_inferior_normalizado,
            limite_superior_normalizado,
        )
        if _resultado_possui_solucao(resultado):
            try:
                modelo.solutions.load_from(resultado)
            except Exception:
                LOGGER.exception(
                    "A solução final não pôde ser carregada; usando a grade inicial viável."
                )
            solucao_otima = terminacao == pyo.TerminationCondition.optimal
        elif terminacao == pyo.TerminationCondition.infeasible:
            LOGGER.error(
                "O modelo completo foi classificado como inviável apesar da solução inicial."
            )
            return 2

    valor_objetivo = pyo.value(modelo.obj_normalizado, exception=False)
    if solucao_otima:
        LOGGER.info("Solução ótima encontrada: objetivo=%s.", valor_objetivo)
    else:
        LOGGER.warning(
            "Solução viável não comprovadamente ótima será utilizada: objetivo=%s.",
            valor_objetivo,
        )

    try:
        alocacoes = atribuir_salas(modelo, dados)
        LOGGER.info(
            "%d ocorrências receberam salas por atribuição canônica.",
            len(alocacoes),
        )
    except Exception:
        LOGGER.exception("Falha durante a atribuição das salas físicas.")
        return 7

    try:
        LOGGER.info("Gerando a grade horária separada por período.")
        imprimir_grade_horaria(modelo, dados)
    except Exception:
        LOGGER.exception("Falha durante a geração do relatório da grade.")
        return 7

    LOGGER.info("Fluxo concluído com sucesso em %.2fs.", perf_counter() - inicio_total)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Interpreta os argumentos e executa o fluxo com tratamento global de falhas."""
    parser = _criar_parser()
    argumentos = parser.parse_args(argv)
    _configurar_logging(argumentos.log_level)

    if argumentos.log_interval <= 0:
        parser.error("--log-interval deve ser maior que zero.")
    if argumentos.time_limit is not None and argumentos.time_limit <= 0:
        parser.error("--time-limit deve ser maior que zero.")
    if argumentos.threads < 0:
        parser.error("--threads não pode ser negativo.")
    if argumentos.mip_gap is not None and not 0 <= argumentos.mip_gap < 1:
        parser.error("--mip-gap deve estar no intervalo [0, 1).")
    if argumentos.mip_abs_gap is not None and argumentos.mip_abs_gap < 0:
        parser.error("--mip-abs-gap não pode ser negativo.")
    if not 0 <= argumentos.heuristic_effort <= 1:
        parser.error("--heuristic-effort deve estar no intervalo [0, 1].")

    try:
        return _executar_fluxo(argumentos)
    except KeyboardInterrupt:
        LOGGER.warning("Execução interrompida pelo usuário.")
        return 130
    except Exception:
        LOGGER.exception("Falha inesperada não tratada no fluxo principal.")
        return 99


if __name__ == "__main__":
    raise SystemExit(main())
