import pyomo.environ as pyo
from websocket import Any


def regra_h1(m: pyo.ConcreteModel, aula_id: str, variaveis_por_aula: dict[str, list[tuple[str, str, str, str]]], aulas: dict[str, dict]) -> Any:
        return sum(m.x[chave] for chave in variaveis_por_aula[aula_id]) == aulas[aula_id]["carga"]

def regra_h3(m: pyo.ConcreteModel, sala: str, dia: str, horario: str,
             variaveis_por_sala_horario: dict[tuple[str, str, str], list[tuple[str, str, str, str]]]) -> Any:
    return sum(m.x[chave] for chave in variaveis_por_sala_horario[(sala, dia, horario)]) <= 1
    
def regra_h4(m: pyo.ConcreteModel, professor: str, dia: str, horario: str,
             variaveis_por_professor_horario: dict[tuple[str, str, str], list[tuple[str, str, str, str]]]) -> Any:
        return sum(m.x[chave] for chave in variaveis_por_professor_horario[(professor, dia, horario)]) <= 1
    

def regra_h5(m: pyo.ConcreteModel, aula_a: str, aula_b: str, dia: str, horario: str,
             variaveis_por_aula: dict[str, list[tuple[str, str, str, str]]]) -> Any:
        variaveis_a = [m.x[chave] for chave in variaveis_por_aula[aula_a] if chave[1] == dia and chave[2] == horario]
        variaveis_b = [m.x[chave] for chave in variaveis_por_aula[aula_b] if chave[1] == dia and chave[2] == horario]
        return sum(variaveis_a) + sum(variaveis_b) <= 1