# Design

## Context

Esta change é construída sobre `bootstrap-regression-guard` (mini-alvos). Motivação: ver `proposal.md`. Requisitos: ver `specs/`. Sem Docker local, o collector, o Jaeger e o Phoenix são opcionais. A ingestão principal é por ficheiro ou HTTP directo ao serviço.

## Goals / Non-Goals

**Goals:**
- Diagnósticos auditáveis: cada um aponta para spans e para a regra que o gerou.
- Começar com regras sobre dados observáveis. A IA só resume e nunca decide.

**Non-Goals:**
- Ser um backend de tracing completo (armazenamento a longo prazo, pesquisa full-text de logs). Para isso existem o Phoenix, o Langfuse e o Jaeger.
- Deteção de anomalias com ML nesta change.

## Decisions

### D1 — Modelo interno de span
`Span(trace_id, span_id, parent_id, name, kind, status, start, end, attrs)`, onde `kind` é o tipo semântico obtido por um mapeamento YAML (`retrieve: [retrieve, vector_search, retrieval]`). Guardado em Postgres/SQLite (`traces`, `spans`, `incidents`, `diagnoses`, `feedback`).
- *Porquê o próprio modelo e não guardar OTLP cru:* as regras ficam simples e independentes do produtor.

### D2 — Redacção em pipeline
Regex + validadores (Luhn para cartões, padrões de NIF/IBAN, prefixos de chaves conhecidos) e uma allowlist de atributos seguros. Aplica-se na ingestão, antes de qualquer escrita. Os testes usam fixtures com segredos falsos.

### D3 — Motor de regras
Cada regra é uma classe com `match(trace) -> list[Finding]` e um `evidence_score`. Por exemplo:
- `retrieval_miss`: `retrieve.retrieved_count == 0` ou o top score abaixo do limiar, seguido de `generate` sem abstenção.
- `citation_unsupported`: `verify.unsupported_claims > 0`.
- `rate_limit`: status 429 num span de provider.
- `stale_memory`: memória recuperada com `created_at` mais antigo do que um documento `superseded`.
- `model_output_regression`: o trace pertence a uma run do RegressionGuard com o caso marcado regredido.

As regras são versionadas (`rules_version`) e testadas com traces golden.

### D4 — Ordenação de falhas aninhadas
Ordem por (profundidade/ordem temporal → regras de dependência conhecidas, como `rate_limit` antes de `fallback` antes de `timeout`). O primeiro é o candidato principal. Fica explicado no learn, sem pretensões de causalidade.

### D5 — Resumo por LLM opcional
O LLM recebe só spans redigidos e devolve um resumo com referências `[span:<id>]`. Um validador rejeita as referências inexistentes.

### D6 — Replay
O replay usa o adaptador do alvo em modo `sandbox`: as ferramentas mutáveis são substituídas por stubs, o provider é mock por omissão (real opcional) e o input vem do campo `replay_input` sintético que o SDK grava em cenários de teste. Para traces reais com input redigido devolve `not_replayable`.

### D7 — UI
Vistas adicionadas ao painel do EvalSentinel: lista de incidentes, árvore de spans (componente de árvore/gantt), lado a lado bom/mau e exportação Markdown. Integração opcional: link "abrir no Phoenix" quando configurado.

### D8 — Documentação pedagógica
`docs/learn/forensics/` tem: `01-opentelemetry-traces-spans`, `02-instrumentar-rag-agentes-gateway`, `03-redaccao`, `04-regras-vs-ml`, `05-observacao-vs-hipotese`, `06-falhas-aninhadas`, `07-replay-seguro` e `08-metricas-de-diagnostico`.

## Risks / Trade-offs

- [As regras são frágeis a mudanças de nomes de atributos] → Mapeamento configurável e testes golden por regra.
- [A redacção é incompleta] → Allowlist de atributos e testes com casos adversariais. Limitação documentada.
- [Um replay com provider real custa dinheiro] → Mock por omissão. Real só com flag e tecto.
- [A suite de injecção favorece as regras escritas para ela] → Cenários escritos antes das regras quando possível, e cenários "não vistos" separados para avaliação.

## Migration Plan

Módulo novo e independente. Compose opcional com otel-collector + Phoenix, marcado como não testado localmente.
