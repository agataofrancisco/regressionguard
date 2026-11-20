# Design

## Context

O repositório está vazio. Motivação: ver `proposal.md`. Requisitos: ver `specs/`. O núcleo (datasets, runs, avaliadores, comparação e gates) é também uma biblioteca usada pelo PromptOps, por isso tem de ter uma API pública pequena, estável e versionada. Pedagogicamente, este projecto ensina avaliação de sistemas não determinísticos e estatística aplicada.

## Goals / Non-Goals

**Goals:**
- Um núcleo pequeno: `Dataset → Target → Evaluators → RunStore → Compare → Report`.
- Correr em segundos em mock e em CI sem segredos.

**Non-Goals:**
- Substituir o promptfoo, o Langfuse ou o Phoenix. Integramos e explicamos as diferenças.
- Um painel multiutilizador com autenticação nesta change. O painel é local e só de leitura.

## Decisions

### D1 — Pacote Python + CLI Typer
`src/regressionguard/{datasets,targets,evaluators,runner,store,compare,report,cli}`. O comando é `ai-eval`.
- *Alternativa:* promptfoo (Node/YAML). É óptimo para prompts, mas menos flexível para avaliadores de segurança/SQL e para a estatística emparelhada. Fica uma integração opcional de import.

### D2 — DuckDB para o histórico
Um ficheiro local `regressionguard.duckdb` com as tabelas `runs`, `case_results` e `evaluator_results`. Permite análises SQL rápidas e não precisa de servidor. Os JSON das runs também ficam em `reports/` para auditoria.
- *Alternativa:* Postgres, para o painel multiutilizador futuro. A camada `store` é uma interface para permitir a troca.

### D3 — Estatística
- **Taxa de sucesso por caso** = média sobre as repetições.
- **Diferença emparelhada:** para cada caso, `d_i = pass_rate_cand_i - pass_rate_base_i`. A média de `d` tem um IC 95% por **bootstrap** sobre os casos (10 000 reamostragens, seed fixa).
- Para métricas binárias com 1 repetição: o teste de **McNemar** sobre os pares discordantes (documentar porque é que o emparelhamento importa).
- `insufficient_sample_size` abaixo de `min_cases` (por omissão 30) ou quando o IC contém 0 e é largo.
- *Porquê bootstrap:* não assume normalidade e é fácil de explicar. É uma boa pergunta de entrevista.

### D4 — Gates em YAML
`gates.yaml` com `critical` (por exemplo `security_violations_new == 0`, `critical_pass_rate_drop <= 0.02`) e `warning` (`p95_latency_increase <= 0.10`, `cost_per_case_increase <= 0.15`). São avaliados sobre o resultado do compare, e a CLI devolve o código de saída.

### D5 — Avaliadores como plugins
Uma interface `Evaluator.evaluate(case, output) -> EvalResult(passed, score, reason, details)` com um registo por nome, declarado no dataset. O `sql_read_only` usa sqlglot (AST: só `SELECT`, sem múltiplos statements e sem funções perigosas).

### D6 — Juiz LLM
Rubrica em ficheiro versionado. Calibração: amostra com labels humanos e cálculo de concordância (Cohen's kappa). É reportado à parte e nunca entra nos gates críticos.

### D7 — Mini-alvos
`targets/extraction/` e `targets/minirag/` com configurações `v1` (baseline) e as variantes regredidas do laboratório (`no-citations`, `unauthorized-select`, `schema-change` e `k1`). O mock é determinístico: regras e respostas derivadas do input com hash. Em modo live usa um provider compatível com OpenAI.

### D8 — CI
`.github/workflows/eval.yml`: no PR corre mock smoke e compara com o artefacto baseline do `main` (guardado como artifact). Um `workflow_dispatch` manual corre o live com o segredo e `--max-usd`. Em PRs de fork não há segredos (comportamento por omissão do GitHub, documentado).

### D9 — Painel
Começa com um HTML estático gerado (Jinja2) e um índice das runs. Um painel Streamlit opcional lê o DuckDB. A escolha deliberada de começar estático é para evitar servidor e auth nesta fase.

### D10 — Documentação pedagógica
`docs/learn/` tem: `00-visao-geral`, `01-porque-avaliar-llms-e-diferente`, `02-goldens-e-labels`, `03-avaliadores-deterministicos`, `04-avaliadores-semanticos`, `05-llm-as-judge-e-calibracao`, `06-aleatoriedade-e-repeticoes`, `07-comparacao-emparelhada-bootstrap-mcnemar`, `08-gates-e-ci`, `09-laboratorio-de-regressoes` e `10-perguntas-de-entrevista`.

## Risks / Trade-offs

- [O mock determinístico não reflecte a variabilidade real] → As repetições e as estatísticas só têm significado em live. Os relatórios mock dizem-no.
- [Poucos casos geram falsos positivos ou negativos] → `insufficient_sample_size` e a taxa de falsos positivos medida no laboratório.
- [Gates demasiado rígidos bloqueiam PRs legítimos] → Separação crítico/aviso e limiares versionados e revistos.
- [Custo de runs live] → `--max-usd` obrigatório e só em job manual.

## Migration Plan

Projecto novo. O baseline inicial é criado com `ai-eval run --suite full --mode mock` e marcado `baseline`.
