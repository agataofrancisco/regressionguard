# Design

## Context

Esta change é construída sobre `bootstrap-regression-guard` (runs, comparação e gates). Motivação: ver `proposal.md`. Requisitos: ver `specs/`.

## Goals / Non-Goals

**Goals:**
- Prompts com o mesmo rigor que o código: imutabilidade, revisão, testes e rollback.
- Um A/B correcto (atribuição estável, sem duplicados) e honesto (sem vencedores prematuros).

**Non-Goals:**
- Substituir o Langfuse. Pode existir sincronização opcional.
- Testes sequenciais e bandits adaptativos. Ficam citados como evolução.

## Decisions

### D1 — Imutabilidade na base de dados
`prompt_versions` não tem UPDATE na camada de repositório e tem um trigger/constraint que o impede (em Postgres) e um `content_hash` UNIQUE por prompt. Os aliases ficam numa tabela à parte com `version_id` e `lock_version` (optimistic locking): um `UPDATE ... WHERE lock_version = n` sem linhas afectadas dá 409.

### D2 — Templates
Jinja2 em `SandboxedEnvironment` com `StrictUndefined`. As variáveis são declaradas em schema Pydantic gerado a partir da declaração. É o mesmo render usado em offline e online, para não haver divergência.

### D3 — Atribuição
`bucket = int(sha256(f"{experiment_id}:{user_id}")[:8], 16) % 10000`. A variante é escolhida pelos limites cumulativos. **Para manter a estabilidade quando as percentagens mudam**, a primeira atribuição é persistida (`assignments` UNIQUE(experiment, user)) e reutilizada. O hash só decide utilizadores novos. Explicar o trade-off com o "rebalanceamento" no learn.

### D4 — Exposições idempotentes
`exposures` com UNIQUE(`idempotency_key`), onde a chave vem do cliente ou de `hash(experiment, user, request_id)`.

### D5 — Estatística
Taxa binária: diferença de proporções com IC (Wilson/Newcombe). Métricas contínuas: bootstrap. `insufficient_sample_size` abaixo do tamanho mínimo calculado a priori (power analysis simples para o MDE configurado) ou quando o IC contém 0. Nada de "espreitar" para declarar um vencedor: o aviso sobre o peeking fica documentado.

### D6 — Gates
Reutiliza `regression-comparison`: a promoção chama `compare(baseline=versão_actual, candidate=nova)` sobre o dataset congelado e aplica `gates.yaml`.

### D7 — Prompts no repositório
`prompts/<nome>.yaml` (template, variáveis, modelo, settings). A Action faz o diff dos ficheiros alterados, cria as versões candidatas no registo efémero do CI (SQLite) e corre o compare em mock. O merge no main pode publicar versões no registo real, num passo opcional manual.

### D8 — Documentação pedagógica
`docs/learn/promptops/` tem: `01-prompts-como-codigo`, `02-imutabilidade-e-aliases`, `03-optimistic-locking`, `04-atribuicao-ab-por-hash`, `05-estatistica-ab-e-peeking`, `06-gates-e-rollback` e `07-ci-de-prompts`.

## Risks / Trade-offs

- [Settings diferentes tornam a comparação injusta] → Recusa por omissão (`unfair_comparison`).
- [Testes A/B com pouco tráfego numa demo] → Simulação com utilizadores sintéticos claramente rotulada.
- [Atribuição persistida cresce com os utilizadores] → É aceitável. Limpa-se no fim da experiência.
- [O CI não deve publicar versões sem revisão] → A publicação é manual após o merge.

## Migration Plan

Módulo novo. Os prompts dos mini-alvos passam a ser lidos do registo, com fallback para o ficheiro local quando o registo não está configurado.
