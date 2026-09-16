import json
from pathlib import Path

def carregar_dados(caminho_aulas: str, caminho_slots: str):
    """Carrega os arquivos JSON de aulas e slots disponíveis."""
    with open(caminho_aulas, 'r', encoding='utf-8') as f:
        aulas_raw = json.load(f)
        
    with open(caminho_slots, 'r', encoding='utf-8') as f:
        slots_raw = json.load(f)

    # Identificador único para cada registro de aula
    aulas = {}
    for idx, item in enumerate(aulas_raw):
        key = f"AULA_{idx}_{item['disciplina']}_{item.get('subturma', 'UNICA')}"
        aulas[key] = {
            'disciplina': item['disciplina'],
            'professor': item['professor'],
            'local_tipo': item['local'],
            'periodo': item['periodo'],
            'carga': item['aulas'],
            'subturma': item.get('subturma', None)
        }

    # Salas físicas e mapeamento de slots válidos (sala, dia, horario)
    salas_fisicas = set()
    salas_por_tipo = {}
    slots_validos = set()  # (sala, dia, horario)

    for item in slots_raw:
        sala = item['local']
        tipo = item['tipo']
        dia = item['dia']
        horario = item['horario']

        salas_fisicas.add(sala)
        salas_por_tipo.setdefault(tipo, set()).add(sala)
        slots_validos.add((sala, dia, horario))

    return {
        'aulas': aulas,
        'salas_fisicas': list(salas_fisicas),
        'salas_por_tipo': salas_por_tipo,
        'slots_validos': slots_validos
    }