# Proposal

## Why

Na maioria das equipas, os prompts vivem em strings espalhadas pelo código, mudam sem revisão e ninguém sabe qual a versão em produção nem se a nova é melhor. O PromptOps trata prompts como artefactos de software: versões imutáveis, aliases (`staging`, `production`), testes offline sobre datasets congelados, **policy gates** que bloqueiam promoções más, A/B online com atribuição estável e kill switch, e integração com GitHub Actions. O Langfuse já oferece versionamento e experiências de prompts. O diferencial aqui são os gates de política reutilizando o RegressionGuard, a integração CI e as análises reproduzíveis com aviso honesto de amostra insuficiente.

Domínio dos exemplos: os prompts dos mini-alvos do EvalSentinel (extracção de encomendas e mini RAG de FAQ).

## What Changes

- Novo módulo `evalsentinel.promptops` com API FastAPI e Postgres (SQLite em demo).
- Entidades `Prompt`, `ImmutableVersion`, `Alias`, `Dataset`, `Experiment`, `Assignment`, `EvaluationRun` e `AuditEvent`, com dono/tenant e controlo de acesso.
- Experiências offline (todas as versões sobre o mesmo dataset congelado com ≥80 exemplos, mesmos modelos e settings) com os gates do RegressionGuard.
- A/B online com atribuição determinística por `hash(experiment_id, user_id)`, percentagens configuráveis, exposições sem duplicados, consentimento para recolher feedback e kill switch.
- Promoção de aliases só depois de passar os gates, com rollback imediato e auditoria.
- GitHub Action: um PR que altera um prompt corre a avaliação e bloqueia se falhar.
- Painel: editor com variáveis tipadas, diff de versões, matriz de resultados, custos, latências, vencedores (com `insufficient_sample_size` quando aplicável) e rollback. Exportação YAML/JSON.

## Capabilities

### New Capabilities
- `prompt-registry`: prompts, versões imutáveis, variáveis tipadas, aliases, controlo de acesso e auditoria.
- `prompt-experiments`: experiências offline e online, atribuição estável, exposições, resultados e kill switch.
- `promotion-gates`: gates de não-regressão, promoção de aliases, rollback e integração CI.

### Modified Capabilities
<!-- Nenhuma: reutiliza regression-comparison e eval-runs sem alterar requisitos. -->

## Impact

- **Código**: `src/evalsentinel/promptops/`, `apps/promptops_api/`, `.github/workflows/promptops.yml` e vistas no painel (React/Next.js ou extensão do painel existente).
- **Dependências**: FastAPI, SQLAlchemy/Alembic, Jinja2 (render de templates com variáveis tipadas), e Redis opcional para cache de resolução.
- **Depende de** `bootstrap-regression-guard`. Integração opcional com Langfuse documentada.
