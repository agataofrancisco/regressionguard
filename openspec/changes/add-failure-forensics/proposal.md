# Proposal

## Why

Quando uma aplicação RAG, um agente ou um gateway de LLMs falha, raramente há um stack trace claro. O problema pode estar no retrieval que não encontrou nada, numa citação sem suporte, num timeout do provider, num schema inválido ou numa tentativa de injecção. Hoje isto investiga-se à mão, span a span. O FailureForensics acrescenta ao EvalSentinel um sistema que importa traces, detecta falhas por regras determinísticas sobre dados observáveis, apresenta a timeline e **hipóteses** de causa (nunca causalidade apresentada como facto) e permite reproduzir o caso num sandbox sem efeitos reais.

## What Changes

- Novo módulo `evalsentinel.forensics` com API: `/traces/import`, `/incidents`, `/incidents/{id}`, `/incidents/{id}/replay`, `/incidents/{id}/feedback` e `/metrics`.
- Ingestão de traces OTLP/JSON e de JSON sintético, com redacção de segredos e PII nos atributos e payloads antes de guardar.
- Um SDK de instrumentação de exemplo para RAG (`ingest`, `retrieve`, `rerank`, `generate`, `verify`), agentes (tool calls, approvals) e gateway (routing, failover), aplicado aos mini-alvos do RegressionGuard.
- Uma taxonomia de 10 tipos de falha com regras determinísticas e scores de evidência. Cada diagnóstico separa `observed_evidence`, `probable_hypothesis`, `confidence_method`, `recommended_check` e `replay_id`.
- Incidentes versionados, feedback de falso positivo e replay de input sintético isolado.
- Uma UI com a lista de incidentes, filtros, a árvore de spans, a comparação bom vs mau e um relatório Markdown.
- Uma suite de fault injection com 8 ou mais cenários e labels golden do passo real de falha.
- Integração opcional com Arize Phoenix ou Langfuse para visualização, sem duplicar o collector.

## Capabilities

### New Capabilities
- `trace-ingestion`: importação de traces OTLP/JSON, normalização, redacção e associação a trace IDs.
- `failure-detection`: taxonomia, regras determinísticas, scores de evidência e diagnósticos que separam observação de hipótese.
- `incident-management`: incidentes, versões, feedback, replay em sandbox e relatórios.
- `forensics-evaluation`: suite de fault injection, labels golden e métricas de classificação e localização.

### Modified Capabilities
<!-- Nenhuma alteração de requisitos às capabilities existentes. -->

## Impact

- **Código**: `src/evalsentinel/forensics/`, `src/evalsentinel/instrumentation/`, `apps/forensics_api/`, `datasets/faults/` e vistas novas no painel.
- **Dependências**: OpenTelemetry SDK e proto OTLP, FastAPI e SQLAlchemy (Postgres ou SQLite em demo). O Phoenix é opcional.
- **Depende de** `bootstrap-regression-guard` (mini-alvos e runner).
- **Infraestrutura opcional**: collector OTel + Jaeger/Phoenix via compose, não testado localmente sem Docker.
