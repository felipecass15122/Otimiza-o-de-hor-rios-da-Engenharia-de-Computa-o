# OT1 — Otimização dos Horários da Engenharia de Computação

Trabalho da disciplina de Otimização I do CEFET-MG Campus Timóteo. O objetivo é formular e resolver, com Python e Pyomo, um modelo de Programação Linear Inteira Mista para alocar aulas, salas e horários sem conflitos.

## Estado atual

O projeto está na etapa de fundação: estrutura do repositório, dados de entrada, ambiente Python e roteiro do notebook. O modelo ainda não foi implementado.

## Pré-requisitos

- Python 3.12
- GLPK instalado localmente e disponível no `PATH` (`glpsol`)

## Ambiente

No PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
glpsol --version
jupyter lab
```

O GLPK não é instalado pelo `pip`; instale-o pelo gerenciador apropriado do seu sistema e confirme que `glpsol --version` funciona antes de resolver o modelo.

## Estrutura

```text
data/raw/              Dados JSON originais e imutáveis.
docs/referencias/      Enunciado fornecido para consulta.
outputs/               Resultados gerados, não versionados.
src/horarios_ec/       Código reutilizável do projeto nas próximas etapas.
tests/                 Testes de dados, modelo e relatórios nas próximas etapas.
Notebook.ipynb         Entrega principal e roteiro da solução.
```

## Próximas etapas

1. Validar e pré-processar os dados.
2. Confirmar a interpretação da restrição H2 antes de implementá-la.
3. Modelar as restrições fortes e as restrições suaves S1 e S2.
4. Resolver com GLPK e gerar grades por sala e por período.
5. Consolidar o notebook e preparar o `Slide.pdf`.
