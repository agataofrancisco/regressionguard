# Integrações opcionais

Nesta change estas integrações estão **apenas documentadas**. Não há código de integração no repositório.
O funcionamento base (datasets, alvos mock, avaliadores, runs, comparação, gates, relatórios, CI) não as
requer nem as importa. Qualquer uma pode ser adicionada depois como um adaptador sem alterar o núcleo.

## promptfoo (importar resultados)

- **O que faz melhor:** iteração rápida sobre prompts com YAML, matriz de providers e uma interface de
  comparação pronta. Bom para explorar variantes antes de fixar um golden set.
- **O que o RegressionGuard faz melhor:** avaliadores de segurança com AST (SQL só de leitura, acesso a
  tabelas proibidas), comparação emparelhada com IC e McNemar, gates críticos com código de saída, e histórico
  auditável com `dataset_hash`. O promptfoo não garante que a comparação é emparelhada nem que um gate bloqueia.
- **Integração possível:** importar o JSON de resultados do promptfoo, mapear cada `testCase` para um `Case`
  com `id` estável e reutilizar o `compare`. Só faz sentido se os casos tiverem ids e labels rastreáveis.

## Langfuse (exportar traces e scores)

- **O que faz melhor:** observabilidade em produção: traces de chamadas reais, custo por utilizador, sessões,
  anotações humanas e dashboards de operação.
- **O que o RegressionGuard faz melhor:** decisão antes do deploy, sobre um conjunto fixo de casos, com gates.
  O Langfuse mostra o que aconteceu; o harness decide se uma mudança passa.
- **Integração possível:** exportar cada `CaseRecord` como um trace com `trace_id` (já existe o campo em
  `TargetOutput`) e cada `EvalRecord` como um score. Ligar `trace_id` às runs permite abrir a chamada original.

## Phoenix (exportar traces e avaliações)

- **O que faz melhor:** análise de traces e de embeddings, clusters de falhas e avaliações exploratórias
  com OpenTelemetry.
- **O que o RegressionGuard faz melhor:** o mesmo que com o Langfuse: gates, estatística emparelhada e
  reprodutibilidade por `dataset_hash` e `commit`.
- **Integração possível:** exportar spans OpenTelemetry por caso e repetição, com os atributos do alvo
  (modelo, prompt, `top_k`) e o resultado dos avaliadores.

## Porque a base não depende delas

- As runs são a fonte de verdade: um JSON de auditoria e uma linha no DuckDB por run e caso.
- Uma integração que falha não pode bloquear um gate, nem mudar um resultado já gravado.
- Não reimplementamos o que estas ferramentas fazem bem (UI de experimentação, observabilidade de produção).
