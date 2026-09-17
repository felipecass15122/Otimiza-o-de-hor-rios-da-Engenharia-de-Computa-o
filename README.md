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

## Executar o modelo

Após configurar um solver compatível, execute no ambiente virtual:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m horarios_ec --solver glpk
```

Como alternativa, se o HiGHS estiver instalado no ambiente Python:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m horarios_ec --solver appsi_highs
```

O comando carrega os dados, resolve o modelo e imprime a grade semanal por sala.

## Estrutura

```text
data/raw/              JSONs originais
docs/referencias/      Enunciado
src/horarios_ec/       Código do projeto
  data_loader.py       Leitura, validação e pré-processamento
  model_builder.py     Modelo Pyomo e restrições
  reporting.py         Impressão da grade
  __main__.py          Comando executável
tests/                 Testes automatizados
outputs/               Resultados futuros
Notebook.ipynb         Entrega principal futura
```

## Próximas etapas

1. Validar e pré-processar os dados.
2. Confirmar a interpretação da restrição H2 antes de implementá-la.
3. Modelar as restrições fortes e as restrições suaves S1 e S2.
4. Resolver com GLPK e gerar grades por sala e por período.
5. Consolidar o notebook e preparar o `Slide.pdf`.
