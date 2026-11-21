# Revisão independente (tarefa 7.3)

Data: 2026-11-21. Revisor: supervisor, independente do executor que implementou o código.

## Âmbito

Segredos no CI, custo de execuções live e honestidade estatística, conforme a tarefa 7.3 do `tasks.md`.

## Achados

| # | Área | Achado | Estado |
|---|---|---|---|
| 1 | Custo live | O tecto `--max-usd` só usava o maior custo **já observado**, por isso a primeira chamada, ou uma chamada maior do que as anteriores, podia ultrapassá-lo. Isto viola a spec `eval-runs`, que diz "parar antes de exceder". | Corrigido em `9a38ef5`: cada chamada tem um limite superior calculado antes de ser feita (`max_tokens` obrigatório, prompt estimado em `ceil(chars/3)` tokens). Um alvo sem limite conhecido recusa o modo live. Se o custo real ultrapassar o limite, a run pára com `provider_cost_above_bound`. Há testes que garantem que a chamada que excederia o tecto nunca é feita. |
| 2 | Dashboard | O baseline por omissão era a run mais antiga, e não a marcada `baseline`. | Corrigido em `9a38ef5`. |
| 3 | Segredos no CI | O job de PR corre em modo mock e não usa segredos. Os PRs de forks não recebem segredos. O segredo `REGRESSIONGUARD_API_KEY` só é usado no `workflow_dispatch` manual, com `--max-usd` obrigatório. As `permissions` estão declaradas. | Sem alterações. |
| 4 | Estatística | Bootstrap percentílico emparelhado por caso (95%, 10 000 reamostragens, seed 1234), McNemar exacto para pares discordantes e `insufficient_sample_size` abaixo de `min_cases=30`. As comparações entre modos ou versões de dataset diferentes são recusadas. Está conforme o design D3. | Sem alterações. |
| 5 | Honestidade | Os resultados mock são rotulados (latência sintética, `provider: mock`). Os preços live estão a `null` com TODO, e o modo live recusa correr enquanto não forem preenchidos. | Sem alterações. |

## Limitações que ficam

- O limite de custo assume que um token tem pelo menos 3 caracteres. Um tokenizador que viole isto faz a run parar com `provider_cost_above_bound` em vez de passar o tecto em silêncio.
- O juiz LLM não está ligado à CLI nem calibrado, porque não existe nenhuma amostra humana.
- Nenhuma execução live foi feita, por falta de chaves de API.
