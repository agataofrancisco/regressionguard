# Decisões

Cada decisão indica a alternativa rejeitada e o motivo. As decisões tomadas durante a execução que não estavam
no plano estão marcadas como **(nova)**.

## D1 — Pacote Python e CLI Typer

Pacote `regressionguard` e entry point `ai-eval`. Rejeitado promptfoo como núcleo: é ótimo para prompts,
mas menos flexível para avaliadores de segurança e para estatística emparelhada. Fica como integração opcional.

## D2 — DuckDB para o histórico

Ficheiro local, sem servidor, com SQL. A camada `store` é uma interface, por isso um Postgres é uma troca
futura. A run é reconstruída a partir das tabelas, não de um blob JSON, para que as consultas leiam a mesma fonte.

## D3 — Estatística emparelhada

Diferença por caso, IC por bootstrap sobre casos (10 000 reamostragens, seed 1234) e McNemar exacto sobre os
pares discordantes. Rejeitado o teste t: as diferenças são discretas e o emparelhamento fica implícito.
Ver `learn/07`.

## D4 — Gates em YAML versionado

`config/gates.yaml`. Os gates críticos fazem a CLI sair com 1; os avisos saem com 0.

## D5 — Avaliadores como registo de funções

`register` com nomes únicos. Um avaliador com erro vira `evaluator_error:<tipo>` e não aborta a run.

## D6 — Juiz LLM como sinal secundário

Rubrica versionada com SHA-256, kappa de Cohen para calibração, e nunca decide a passagem de um caso.

## D7 — Mini-alvos com mock determinista

A extração usa regras; o RAG usa recuperação lexical e frases da FAQ. As regressões são configurações YAML.
Rejeitado um LLM no mock: não seria reprodutível nem sem rede.

## D8 — CI

`eval.yml`: smoke em mock nos PRs, comparação com um artefacto `baseline` do `main`, live manual com
`max_usd`. PRs de forks não recebem segredos. Não executado no GitHub (sem acesso); validado como YAML e
simulado localmente.

## D9 — Painel

HTML estático gerado (`ai-eval index`, `report`, `compare --html`) como caminho principal, sem servidor nem
autenticação. Streamlit como painel opcional, só leitura.

## D10 — Documentação pedagógica

`docs/learn/` com um ficheiro por tema, saídas reais e perguntas de entrevista.

## Decisões novas (executor)

- **N1 — Pacote `comparison` em vez de `compare`.** Evita sombrear a função pública `regressionguard.compare`.
- **N2 — Chave e preços.** A chave vem de variável de ambiente; os preços de `params.live` são obrigatórios
  e estão a `null` com `TODO`, para que um live não corra com custo zero por engano.
- **N3 — `--mode live` exige configuração com `params.live`.** Sem ela recusa (`config_not_live`) em vez de
  correr um mock com rótulo de live.
- **N4 — Limiar de passagem por caso = 0.5** (`pass_rate >= 0.5`), para McNemar e para as regressões.
- **N5 — Gate crítico não avaliável falha fechado.** Sem casos críticos, `critical_pass_rate_drop` falha.
- **N6 — Comparação recusada em modos diferentes** (`mode_mismatch`).
- **N7 — Latência sintética do mock** depende do tamanho da entrada e da saída, e é sempre rotulada
  `synthetic-mock`. Sem isto o gate de latência nunca dispararia em mock.
- **N8 — Orçamento com estimativa pelo maior custo observado.** A primeira chamada não tem estimativa e pode
  ultrapassar o teto em uma chamada. Documentado como limitação.
- **N9 — Ordem de avaliadores e casos preservada** na base de dados (coluna `seq`), para que a run recarregada
  seja igual à original.
- **N10 — Verificação de esquema DuckDB** (`StoreSchemaError`) em vez de falha tardia numa base antiga.
- **N11 — Ajuda da CLI em texto simples** (`rich_markup_mode=None`): o render Rich falhava ao escrever em pipes
  do Git Bash no Windows.
- **N12 — `license` removido do `pyproject.toml`.** A licença não foi escolhida pelo utilizador; o campo
  também gerava um aviso de depreciação do setuptools.
- **N13 — Mock de extração e RAG com limiares de passagem definidos nos casos** (`threshold` por omissão 0.9 e 0.7).
  Os valores foram escolhidos antes de medir a baseline e não foram ajustados depois.
- **N14 — Comando `ai-eval import`** para trazer o baseline de um artefacto de CI para a base local.
- **N15 — Gates `new_failures` contam casos.** Um caso conta uma vez mesmo que falhem vários avaliadores do
  mesmo gate; a evidência lista o primeiro avaliador que falhou.
