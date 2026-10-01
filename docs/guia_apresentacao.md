# Guia de Apresentação — Otimização de Horários

## 1. Objetivo

Este trabalho modela a alocação semanal de aulas da Engenharia de Computação
como um problema de Programação Linear Inteira Mista (PLIM), implementado em
Python com Pyomo e resolvido com HiGHS.

O objetivo é definir dia e horário para cada aula, respeitando carga semanal,
tipo de ambiente, disponibilidade de salas, professor e período pedagógico.

## 2. Roteiro curto de fala

1. O problema manual de montar horários possui muitas combinações e conflitos.
2. Os JSONs informam as aulas e os slots de sala já livres.
3. O modelo escolhe horários por meio de variáveis binárias.
4. As restrições fortes impedem conflitos.
5. HiGHS encontra uma solução inteira viável.
6. Um pós-processamento associa as salas físicas reais.
7. O notebook mostra a grade por período e por sala.

## 3. Dados de entrada

| Fonte | Conteúdo |
|---|---|
| `disciplinas_professores_ec.json` | 58 registros de aula/turma; disciplina, professor, período, tipo de ambiente, carga e subturma opcional. |
| `salas_horarios_disponiveis_somente_37_39_labs.json` | 554 slots livres de oito salas físicas. |

A demanda total é de **158 aulas de 50 minutos**.

Os tipos de ambiente são `sala`, `lab_info`, `lab_ce` e `lab_fis`.

## 4. Fluxo de execução

```text
Upload dos JSONs
    ↓
Leitura e pré-processamento
    ↓
Construção do domínio válido
    ↓
Modelo PLIM em Pyomo
    ↓
Resolução com HiGHS
    ↓
Alocação canônica das salas físicas
    ↓
Tabelas por período e por sala
```

O notebook usa `google.colab.files.upload()`. Portanto, ele está pronto para
execução no Google Colab; em Jupyter local, essa célula precisa ser substituída
por caminhos locais.

## 5. Pré-processamento

Cada entrada de aula recebe um identificador interno, como `AULA_000`.

O código cria o domínio de horários:

```text
(aula, dia, horário)
```

Somente são criadas possibilidades quando existe pelo menos uma sala livre do
tipo exigido. Assim, uma aula `lab_info` não recebe decisões em uma sala teórica.

## 6. Formulação matemática

### Variável de decisão

```text
y[a, d, h] ∈ {0, 1}
```

Vale 1 quando a aula `a` é ministrada no dia `d` e no horário `h`.

A sala física não aparece diretamente na variável. O modelo trabalha com a
capacidade por tipo de ambiente; depois da solução, as aulas são distribuídas
nas salas físicas disponíveis.

### H1 — Carga horária

```text
Σ y[a,d,h] = carga(a)
```

Cada aula recebe exatamente sua quantidade semanal de módulos.

### H2 — Compatibilidade de ambiente

Uma aula só entra no domínio se houver sala livre compatível com seu tipo.
Logo, a compatibilidade é garantida estruturalmente.

### H3 — Capacidade de salas

```text
Σ y[a,d,h] ≤ número de salas livres do tipo exigido em (d,h)
```

Não permite mais aulas simultâneas do que salas físicas disponíveis em cada
tipo de ambiente.

### H4 — Conflito de professor

```text
Σ y[a,d,h] ≤ 1
```

Para cada professor e horário, impede duas aulas simultâneas.

### H5 — Conflito de período/turma

A intenção é impedir choque entre aulas do mesmo período, permitindo que G1 e
G2 coincidam. Uma aula sem subturma conflita com ambas.

## 7. Solver e resultado salvo no notebook

O notebook usa:

```python
pyo.SolverFactory("appsi_highs")
```

Configurações:

- limite de tempo: 90 segundos;
- gap relativo máximo: 2%.

Resultado obtido:

| Métrica | Valor |
|---|---:|
| Variáveis binárias | 4.656 |
| Restrições iniciais | 2.371 |
| Solução | `optimal` |
| Gap final | 0% |
| Tempo de solução | aproximadamente 0,27 s |
| Aulas com sala física atribuída | 158 |

O tempo foi muito menor que o limite configurado, e o solver reportou ausência
de violações de integralidade e de restrições.

## 8. Atribuição de salas físicas

Após escolher os horários, `atribuir_salas_canonicas()`:

1. agrupa aulas por tipo, dia e horário;
2. consulta as salas físicas livres;
3. ordena aulas e salas;
4. associa cada aula a uma sala disponível.

Essa etapa funciona porque H3 limita a quantidade de aulas à capacidade de
salas livres daquela categoria.

## 9. Visualização

O notebook gera:

- tabelas azuis por período, com disciplina, professor e sala;
- tabelas verdes por sala, com disciplina, período e professor.

A grade por sala é a melhor demonstração visual de que não existe ocupação
simultânea da mesma sala.

## 10. Principais desafios da construção

1. Interpretar `local` como tipo de ambiente, e não como sala física fixa.
2. Transformar slots livres em um domínio de decisão menor e compatível.
3. Representar capacidade por categoria de sala antes da atribuição física.
4. Tratar subturmas G1/G2 sem bloquear coincidências permitidas.
5. Preservar viabilidade diante de professores e períodos compartilhados.
6. Converter uma solução agregada por tipo em uma grade de salas reais.

## 11. Resultados positivos

- O problema foi resolvido como PLIM binário.
- As 158 aulas receberam alocação física.
- A solução foi encontrada rapidamente.
- H1, H2, H3 e H4 estão representadas de forma coerente com a modelagem.
- A saída por sala e período facilita a inspeção da grade.
- A separação entre otimização e atribuição de salas reduz o tamanho do modelo.

## 12. Limitações e pontos honestos para a apresentação

### Restrições suaves S1 e S3

Embora o notebook nomeie S1 como minimização de janelas e S3 como
balanceamento semanal, as expressões atuais somam variáveis `y` cuja quantidade
já é fixada por H1. Portanto, o valor objetivo atual não mede de fato janelas
nem distribuição entre dias.

O valor objetivo salvo, **424**, não deve ser apresentado como métrica de
qualidade pedagógica. A solução é ótima para a função codificada, mas essa
função ainda não implementa penalidades reais de janelas e balanceamento.

Para implementar S1 e S3 corretamente, seriam necessárias variáveis auxiliares
de ocupação, início/fim do turno, carga diária e desvios absolutos.

### H5 em períodos sem subturmas

Na implementação atual, períodos sem G1/G2 podem não formar grupos de conflito
em H5. Assim, esse caso precisa de ajuste antes de afirmar cobertura completa
de conflito de período para todos os dados.

### Grade por período

A tabela por período armazena uma única entrada por `(período, dia, horário)`.
Caso G1 e G2 coincidam legalmente, uma das entradas pode sobrescrever a outra
na visualização. A grade por sala preserva melhor essa situação.

