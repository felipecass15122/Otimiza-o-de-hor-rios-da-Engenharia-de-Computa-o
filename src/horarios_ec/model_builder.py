import pyomo.environ as pyo

def criar_modelo_otimizacao(dados_carregados: dict) -> pyo.ConcreteModel:
    """Constrói o modelo Pyomo PLIM com as restrições fortes H1-H5."""
    aulas = dados_carregados['aulas']
    salas_por_tipo = dados_carregados['salas_por_tipo']
    slots_validos = dados_carregados['slots_validos']

    model = pyo.ConcreteModel()

    # Conjuntos
    model.AULAS = pyo.Set(initialize=list(aulas.keys()))
    
    dias = {'Seg', 'Ter', 'Qua', 'Qui', 'Sex'}
    horarios = {f'M{i}' for i in range(1, 7)} | {f'T{i}' for i in range(1, 7)} | {f'N{i}' for i in range(1, 6)}
    
    # Gerar tuplas (aula, dia, horario, sala) restritas ao domínio válido
    dominios_validos = []
    for a_id, a_info in aulas.items():
        tipo_exigido = a_info['local_tipo']
        salas_compativeis = salas_por_tipo.get(tipo_exigido, set())
        
        for sala in salas_compativeis:
            for dia in dias:
                for h in horarios:
                    if (sala, dia, h) in slots_validos:
                        dominios_validos.append((a_id, dia, h, sala))

    model.X_DOMINIO = pyo.Set(dimen=4, initialize=dominios_validos)

    # Variável de Decisão
    model.x = pyo.Var(model.X_DOMINIO, domain=pyo.Binary)

    # Função Objetivo Primária
    model.obj = pyo.Objective(expr=1, sense=pyo.minimize)

    # H1: Carga Horária Semanal
    def rule_h1(m, a_id):
        vars_aula = [m.x[a, d, h, s] for (a, d, h, s) in m.X_DOMINIO if a == a_id]
        if not vars_aula:
            return pyo.Constraint.Skip
        return sum(vars_aula) == aulas[a_id]['carga']

    model.H1_CargaHoraria = pyo.Constraint(model.AULAS, rule=rule_h1)

    # H3: Não sobreposição de sala
    slots_unicos_sala = {(s, d, h) for (_, d, h, s) in model.X_DOMINIO}
    
    def rule_h3(m, s, d, h):
        vars_sala = [
            m.x[a, d_i, h_i, s_i]
            for (a, d_i, h_i, s_i) in m.X_DOMINIO
            if s_i == s and d_i == d and h_i == h
        ]
        if not vars_sala:
            return pyo.Constraint.Skip
        return sum(vars_sala) <= 1

    model.H3_NaoSobreposicaoSala = pyo.Constraint(slots_unicos_sala, rule=rule_h3)

    # H4: Conflito de Professor
    professores = {info['professor'] for info in aulas.values()}
    dias_horarios = {(d, h) for (_, d, h, _) in model.X_DOMINIO}

    def rule_h4(m, prof, d, h):
        vars_prof = [
            m.x[a, d_i, h_i, s]
            for (a, d_i, h_i, s) in m.X_DOMINIO
            if d_i == d and h_i == h and aulas[a]['professor'] == prof
        ]
        if not vars_prof:
            return pyo.Constraint.Skip
        return sum(vars_prof) <= 1

    model.H4_ConflitoProfessor = pyo.Constraint(professores, dias_horarios, rule=rule_h4)

    # H5: Conflito de Período/Turma
    grupos_turmas = {(info['periodo'], info['subturma']) for info in aulas.values()}

    def rule_h5(m, per, sub, d, h):
        vars_turma = [
            m.x[a, d_i, h_i, s]
            for (a, d_i, h_i, s) in m.X_DOMINIO
            if d_i == d and h_i == h and aulas[a]['periodo'] == per and aulas[a]['subturma'] == sub
        ]
        if not vars_turma:
            return pyo.Constraint.Skip
        return sum(vars_turma) <= 1

    model.H5_ConflitoPeriodo = pyo.Constraint(grupos_turmas, dias_horarios, rule=rule_h5)

    return model