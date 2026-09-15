# Planejamento — TP01 Otimização de Horários (EC)

Baseado no enunciado [`docs/referencias/enunciado-tp01.pdf`](referencias/enunciado-tp01.pdf) e no estado atual do repositório.

- **Disciplina:** Otimização I (G07OTIM1.01) — Prof. Thiago de Sousa Goveia
- **Prazo:** 01/10/2026 (hoje: 15/09/2026 → ~2 semanas)
- **Valor:** 20 pontos, pontuação individual, com acompanhamento em aula
- **Entregáveis:** `Notebook.ipynb` (modelo PLIM completo) + `Slide.pdf` (processo e resultados)

## 1. Objetivo

Formular e resolver em Pyomo um modelo de Programação Linear Inteira Mista (PLIM) para o
*University Course Timetabling Problem* do curso de Engenharia de Computação (Campus Timóteo),
a partir dos dois JSONs fornecidos, produzindo uma grade semanal sem conflitos por sala e por
período.

## 2. Dados de entrada — diagnóstico

Já levantado a partir de `data/raw/`:

| Arquivo | Conteúdo | Volume |
|---|---|---|
| `disciplinas_professores_ec.json` | aulas a alocar (disciplina, professor, categoria de local, período, carga em aulas de 50min, subturma opcional) | 58 registros, 158 aulas-slot no total, 22 professores |
| `salas_horarios_disponiveis_somente_37_39_labs.json` | slots (sala, tipo, dia, horário) livres para receber aula | 554 slots livres, 8 salas físicas |

Capacidade agregada por categoria (`tipo`/`local`) — checagem de viabilidade grosseira, sem considerar
ainda conflitos de professor/período:

| Categoria | Demanda (aulas) | Slots livres | Salas físicas do tipo |
|---|---|---|---|
| `sala` | 88 | 138 | 37, 39 |
| `lab_info` | 54 | 248 | 20‑INF IV, 23‑ENGSOFT, 40‑INF III, 47‑INF I |
| `lab_ce` | 12 | 85 | 24‑CE |
| `lab_fis` | 4 | 83 | Lab Física |

A folga é confortável em nível agregado; o risco real de inviabilidade está nas restrições H3–H5
(concorrência de professor/período em horários específicos), não na capacidade bruta.

## 3. Decisões de modelagem a fechar antes de codificar

Estas são as pendências que o README já sinaliza ("Confirmar a interpretação da restrição H2") e que
devem ser resolvidas — e documentadas no notebook — antes da formulação:

1. **Interpretação de H2 (Alocação Exclusiva de Sala).** O campo `local` de cada disciplina é uma
   **categoria** (`sala`, `lab_info`, `lab_ce`, `lab_fis`), não uma sala física específica — e o
   `tipo` de cada slot usa o mesmo vocabulário. Logo H2 não fixa uma sala única, e sim restringe a
   variável `x_{d,t,s}` a salas `s` cujo tipo bate com o `local` da disciplina `d`. Ex.: uma aula com
   `local: "lab_info"` pode cair em qualquer um dos 4 laboratórios de informática. Isso deve ficar
   explícito no domínio de `s` (ou zerando `x_{d,t,s}` fora do conjunto compatível).
2. **Normalização de `periodo`.** Os valores não são consistentes: `"EC8"` e `"EC8 - 2023"`
   aparecem como períodos distintos (idem `"EC9"`, `"EC10"` sem sufixo de ano, enquanto os demais têm
   `" - 2023"`). Definir uma função de normalização (ex.: extrair só o prefixo `ECx`) antes de aplicar
   H5, para não tratar o mesmo período pedagógico como dois períodos diferentes.
3. **Granularidade de H5 (Conflito de Período/Turma).** Confirmar que a chave de conflito é
   `periodo` normalizado, com exceção quando `subturma` difere (G1 x G2 podem coincidir no tempo).
4. **Pesos `w_i` das restrições fracas** — arbitrários por enunciado; escolher valores que não
   dominem a viabilidade (as fracas nunca podem inviabilizar uma solução que satisfaça as fortes).

## 4. Conjuntos e parâmetros

- `D` — dias úteis `{Seg, Ter, Qua, Qui, Sex}`
- `H` — módulos de horário `{M1..M6, T1..T6, N1..N5}`
- `T = D × H` — slots de tempo
- `Aulas` — índice das aulas/disciplinas-subturma (linha do JSON de disciplinas), chave natural
  `(disciplina, periodo_normalizado, subturma)`
- `Salas` — salas físicas derivadas do JSON de slots (`37`, `39`, `20‑INF IV`, `23‑ENGSOFT`,
  `24‑CE`, `40‑INF III`, `47‑INF I`, `Lab Física`)
- `livre(s, t) ∈ {0,1}` — slot `(s,t)` disponível (deriva da lista de slots livres)
- `tipo(s)` — categoria da sala `s`
- `local(d)` — categoria exigida pela aula `d`
- `professor(d)`, `periodo(d)`, `subturma(d)`, `carga(d)` (campo `aulas`)

## 5. Variável de decisão

```
x[d, t, s] ∈ {0,1}   1 se a aula d é alocada no slot t=(dia,horário) e sala s
```

Domínio restrito por pré-processamento: só criar `x[d,t,s]` quando `livre(s,t) = 1` e
`tipo(s) == local(d)` (reduz drasticamente o número de variáveis).

## 6. Restrições fortes

| # | Nome | Formulação |
|---|---|---|
| H1 | Carga horária semanal | `Σ_{t,s} x[d,t,s] = carga(d)`, ∀d |
| H2 | Alocação exclusiva de sala | garantida por construção do domínio de `s` (tipo compatível) |
| H3 | Não sobreposição de sala | `Σ_d x[d,t,s] ≤ 1`, ∀(t,s) |
| H4 | Conflito de professor | `Σ_{d: professor(d)=p} Σ_s x[d,t,s] ≤ 1`, ∀p, ∀t |
| H5 | Conflito de período/turma | `Σ_{d: periodo(d)=k, subturma(d)=g} Σ_s x[d,t,s] ≤ 1`, ∀(k,g), ∀t — agrupando por
(período, subturma), tratando ausência de subturma como grupo único |

## 7. Restrições fracas (mínimo 2 — recomendação: S1 + S3)

- **S1 — Janelas por período:** variável auxiliar de "ocupado" por (período, dia, horário);
  penalizar slots vazios entre o primeiro e o último horário ocupado do dia.
- **S3 — Balanceamento semanal:** penalizar desvio do número de aulas por dia em relação à média
  do período (ex.: `Σ_dia |aulas_dia − média|` linearizado com variáveis auxiliares, ou variância
  aproximada por penalidade de excesso acima de um teto).

S2 e S4 ficam como extensão opcional se houver tempo, já que o enunciado exige apenas 2.

## 8. Função objetivo

```
min Z = w1 * S1 + w3 * S3
```

Começar validando o modelo com `min Z = 1` (viabilidade pura) antes de introduzir as fracas —
como o próprio enunciado recomenda — para isolar bugs de restrições fortes de bugs da função
objetivo.

## 9. Plano de execução (mapeado às seções já existentes em `Notebook.ipynb`)

1. **Contexto e objetivo** — colar o resumo das seções 1–3 deste documento.
2. **Dados de entrada** — carregar os dois JSONs, documentar campos (já feito aqui, replicar como
   texto/tabela no notebook).
3. **Validação e pré-processamento**
   - normalizar `periodo`;
   - construir `Salas`, `tipo(s)`, `livre(s,t)`;
   - construir índice de aulas com chave `(disciplina, periodo, subturma)`;
   - checar duplicatas e consistência de professores/tipos.
4. **Formulação PLIM** — declarar `ConcreteModel`, `Set`s, `Param`s, `Var` `x[d,t,s]` restrita ao
   domínio pré-filtrado.
5. **Restrições fortes** — implementar H1, H3, H4, H5 (H2 embutida no domínio).
6. **Restrições fracas** — implementar S1 e S3 com variáveis auxiliares; validar pesos.
7. **Solução e relatórios**
   - resolver com GLPK (`glpsol`, já é o solver adotado no README);
   - checar status do solver (`ok`/`optimal`, `infeasible`);
   - exportar grade por sala (linhas = dia×horário, colunas = salas) e por período.
8. **Slide.pdf** — desafios de modelagem (H2/normalização de período), resultados (viável? quantas
   janelas restaram?), decisões de peso.

## 10. Estrutura do repositório (atual, para referência)

```text
data/raw/              JSONs originais, imutáveis.
docs/referencias/      Enunciado.
docs/planejamento.md   Este documento.
outputs/               Resultados gerados (grade exportada), não versionado.
src/horarios_ec/       Código reutilizável (carregamento, normalização, modelo, relatórios).
tests/                 Testes de pré-processamento e do modelo.
Notebook.ipynb         Entrega principal.
requirements.txt       pyomo, pandas, jupyterlab, ipykernel, pytest.
```

`src/horarios_ec/` e `tests/` ainda estão vazios (`.gitkeep`) — a recomendação é extrair para lá
as funções de carregamento/normalização/relatório usadas no notebook, testando-as com `pytest`
(ex.: normalização de período, filtro de domínio `x[d,t,s]`), e importar essas funções no notebook
em vez de duplicar lógica em células.

## 11. Cronograma sugerido (até 01/10/2026)

| Data alvo | Entrega |
|---|---|
| 18/09 | Pré-processamento validado (seções 2–3 do notebook) + testes básicos |
| 22/09 | Modelo com restrições fortes resolvendo com `min Z = 1` (viabilidade confirmada) |
| 25/09 | Restrições fracas S1 e S3 incorporadas, pesos ajustados |
| 27/09 | Exportação da grade por sala/período revisada |
| 29/09 | Slide.pdf com desafios e resultados |
| 01/10 | Entrega final |

## 12. Riscos e pontos de atenção

- Inconsistência de `periodo` pode mascarar violações de H5 se não normalizada.
- Domínio de `x[d,t,s]` sem filtro por `tipo(s) == local(d)` e por `livre(s,t)` explode o número de
  variáveis (8 salas × 554 slots × 58 aulas ≈ 257k sem filtro) — filtrar antes de declarar o `Var`.
- Pesos das restrições fracas mal calibrados podem tornar o solver lento sem ganho perceptível de
  qualidade — validar com poucos pesos primeiro.
- GLPK precisa estar no `PATH` (`glpsol --version`) — já documentado no README.
