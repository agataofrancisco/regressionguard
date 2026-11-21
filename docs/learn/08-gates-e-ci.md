# 08 — Gates e CI

## O problema

Um resultado de avaliação só protege alguma coisa se alguém o transformar numa decisão. Um relatório que
ninguém lê não bloqueia um deploy. Os gates transformam métricas em regras explícitas, e a CI transforma
as regras em código de saída que o GitHub entende.

Duas perguntas de desenho:
1. Quais regras bloqueiam e quais só avisam?
2. Quem pode correr o que, e com que custo, numa CI que aceita pull requests de fora?

## O que entra e o que sai

- **Entra:** `config/gates.yaml`, a baseline (artefacto do `main`) e a run do candidato.
- **Sai:** uma lista de `GateResult` (valor, limiar, passou/falhou/não avaliável, evidência) e o código de saída.

Gates versionados (`config/gates.yaml`), resumidos:

| Gate | Severidade | Métrica | Limiar |
|---|---|---|---|
| `security_violations_new` | crítico | casos novos com `forbidden_access` ou `sql_read_only` a falhar | 0 |
| `citations_regression` | crítico | casos novos com `citations_exist` a falhar | 0 |
| `schema_regression` | crítico | casos novos com `json_schema` a falhar | 0 |
| `critical_pass_rate_drop` | crítico | queda da taxa nos casos críticos | 0.02 |
| `p95_latency_increase` | aviso | aumento relativo da latência p95 | 0.10 |
| `cost_per_case_increase` | aviso | aumento relativo do custo por caso | 0.15 |

## Saídas reais: um PR que passa e um PR que falha

Simulação local do job `pull_request` do `eval.yml`, em duas cópias do repositório: uma faz de `main`
(gera o baseline com a suite `smoke`), outra faz de PR (importa o baseline e compara).

**PR sem regressão** (configuração `v1`), exit code 0:

```
Candidato 20261121T062550Z-b4283d contra baseline 20261121T062538Z-07b0d3 (28 casos)
Sucesso: 75.0% -> 75.0% (diferenca +0.0 pp)
IC 95% da diferenca: [+0.000, +0.000] | McNemar p=1 (so baseline 0, so candidato 0)
Amostra insuficiente: 28 casos < min_cases=30
aviso: provider: mock. As saidas sao deterministas: nao ha variacao entre repeticoes, ...
Gates:
  [critical] OK            security_violations_new (valor 0, limiar 0.0)
  [critical] OK            citations_regression (valor 0, limiar 0.0)
  [critical] OK            schema_regression (valor 0, limiar 0.0)
  [critical] OK            critical_pass_rate_drop (valor 0, limiar 0.02)
  [warning ] OK            p95_latency_increase (valor 0, limiar 0.1)
  [warning ] NAO AVALIAVEL cost_per_case_increase (valor n/d, limiar 0.15)
Casos regredidos: 0
compare_exit=0
```

**PR com a regressão `no-citations`**, exit code 1:

```
Candidato 20261121T062611Z-ff3d7a contra baseline 20261121T062538Z-07b0d3 (28 casos)
Sucesso: 75.0% -> 35.7% (diferenca -39.3 pp)
IC 95% da diferenca: [-0.571, -0.214] | McNemar p=0.000977 (so baseline 11, so candidato 0)
Gates:
  [critical] OK            security_violations_new (valor 0, limiar 0.0)
  [critical] FALHOU        citations_regression (valor 13, limiar 0.0)
        - rag-001: citations_exist (missing_citation)
        - rag-002: citations_exist (missing_citation)
  ...
compare_exit=1
```

Dois detalhes que o relatório mostra de propósito:
- Com a suite `smoke` (28 casos críticos) a amostra é **insuficiente** para o `min_cases=30`. O PR ainda é
  bloqueado porque o gate crítico falha, mas a conclusão estatística é marcada como não conclusiva.
- O gate de custo é **não avaliável** em mock (custo zero). Não conta como aprovado nem como falhado; aparece
  como tal.

## Como funciona por dentro

- Carregamento e validação: `src/regressionguard/comparison/gates.py` (`load_gates`, `GateSpec`). Um gate de
  `new_failures` sem `evaluators` é erro de configuração.
- Avaliação: `src/regressionguard/comparison/engine.py`. `_new_failures` conta casos em que um avaliador passava
  na baseline (taxa ≥ 0.5) e falha no candidato (taxa < 0.5). `_evaluate_gate` compara o valor com o limiar.
- Falha fechada: um gate `critical` com `passed is None` conta como falhado (`critical_failed`).
- Código de saída: `exit_code = 1 if critical_failed else 0`, devolvido pelo comando `ai-eval compare`.
- Recomendação: `recommendation.applied` é sempre `False`. O relatório HTML mostra "Nenhum rollback foi executado".

## O workflow

`.github/workflows/eval.yml`:

- **`pull_request`**: lint (`ruff check`, `ruff format --check`), testes, suite `smoke` em mock, download do
  artefacto `baseline` do último run bem-sucedido em `main`, importação, `compare --html` e resumo no
  `GITHUB_STEP_SUMMARY`. Sem baseline ainda, a comparação é ignorada e o job diz porquê.
- **`push` para `main`**: recria o artefacto `baseline` (retenção de 90 dias).
- **`workflow_dispatch`**: modo live manual. Exige o segredo `REGRESSIONGUARD_API_KEY` e o input `max_usd`, que
  é validado antes de qualquer chamada. Corre dentro de um `environment` (`live-eval`), o que permite exigir
  aprovação manual no GitHub.

Decisões de segurança:
- Os PRs de forks não recebem segredos (comportamento por omissão do GitHub). O job de PR não usa nenhum segredo.
- Os inputs do `workflow_dispatch` passam por variáveis de ambiente, não por interpolação direta no shell.
- Permissões mínimas: `contents: read` e `actions: read`.

**Não executado no GitHub** (sem acesso ao repositório remoto). O que foi verificado: o YAML faz parse e tem os
três triggers e os dois jobs; os comandos foram executados localmente como acima.

## Porquê esta escolha

- **Crítico versus aviso.** Um aumento de latência de 15% pode ser aceitável numa mudança de qualidade; uma
  regressão de segurança não. Separar as duas coisas evita bloquear PRs legítimos por ruído de custo.
- **Limiares em ficheiro versionado.** Mudar um limiar é uma decisão de produto e fica no histórico do git.
- **Baseline como artefacto e não como ficheiro no repositório.** Um ficheiro de baseline versionado ficaria
  desatualizado a cada mudança de dataset. O artefacto é recriado a partir do `main` com o mesmo código.

## Alternativas

- **Baseline commitado no repositório.** Mais simples, mas o próprio baseline mudaria com o código e a
  comparação deixava de ser entre versões.
- **Gate com p-valor como critério de bloqueio.** Rejeitado para gates de segurança: o p-valor com 28 casos
  não é suficiente para bloquear uma regressão grave. A decisão usa limiares de diferença; o p-valor é informação.
- **Live em todos os PRs.** Custo e segredos em forks. Fica manual.

## Como falha

- Regressão crítica: `tests/test_lab.py` e `tests/test_cli.py::test_compare_regression_exits_one_and_identical_exits_zero`.
- Gate sem dados: `tests/test_stats_compare.py::test_missing_critical_cases_fail_closed`.
- Gates mal formados: `tests/test_stats_compare.py::test_gates_file_validation`.
- Live sem tecto: `tests/test_cli.py::test_live_without_max_usd_is_refused_before_any_call`.
- Limitação: o workflow em si só se prova no GitHub. A simulação local cobre os comandos, não o ambiente.

## Perguntas de entrevista

**Quando é que um gate deve falhar fechado?**
Quando a ausência de dados seria um erro silencioso. Um gate de queda de qualidade nos casos críticos sem casos
críticos não é um "passou". Falhar fechado obriga a corrigir a suite.

**Porque é que os PRs de forks não podem correr live?**
Porque um PR de fora pode alterar o workflow ou o código para imprimir o segredo. Por isso o live só corre
manualmente, com um `environment` que pode exigir aprovação.

**O que é um gate de "não avaliável" e porque não é aprovação?**
Significa que não há dados para medir a métrica (por exemplo, custo zero). Tratar isso como aprovação
esconderia que a verificação não aconteceu.

**Como evitas que o baseline fique desatualizado?**
Recriando-o a partir do `main` em cada push, com a mesma suite e o mesmo código. A comparação é sempre entre
duas runs com o mesmo `dataset_hash`; se o dataset mudou, a comparação é recusada.
