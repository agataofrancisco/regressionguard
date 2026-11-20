# Design

## Context

Esta change é construída sobre `bootstrap-regression-guard` (datasets, runs, store e avaliadores). Motivação: ver `proposal.md`. Requisitos: ver `specs/`.

## Goals / Non-Goals

**Goals:**
- Uma decisão por campo explicável: dá para mostrar o "porquê" de cada valor aceite ou recusado.
- Uma experiência que pode concluir "não vale a pena arbitrar" se for isso que os dados mostram.

**Non-Goals:**
- OCR de imagens de documentos. O input já é texto.
- Treinar modelos de calibração complexos. Começamos com métodos simples.

## Decisions

### D1 — Pipeline
`generate (paralelo, asyncio.gather com timeout) → validate schema → normalize → locate evidence → score → decide → (verify | review | abstain)`.

### D2 — Localização de evidência
Para cada valor normalizado, geram-se as suas formas textuais possíveis (por exemplo, a data 2026-02-03 → "03/02/2026", "3-2-2026", "3 de fevereiro de 2026"; o montante 1250.5 → "1.250,50", "1250,50 €") e procuram-se no texto normalizado com mapeamento de offsets para o original. Há fuzzy matching só para matrículas e nomes, com um limiar.
- *Porquê:* é determinístico, auditável e não depende de outro LLM.

### D3 — Score e decisão
`confidence(valor) = f(acordo, evidência, fiabilidade)`. Começa com uma regressão logística sobre três features, treinada no split de calibração, porque é simples, explicável e dá probabilidades. Alternativa: uma regra ponderada fixa como baseline. Os limiares `accept ≥ τ_a`, `verify` entre `τ_v` e `τ_a`, e abaixo disso `human_review`/`abstain` conforme a política e o orçamento. A calibração é medida com reliability diagram e ECE.

### D4 — Fiabilidade histórica
Uma tabela `(modelo, campo) → acertos/total` com prior Beta, alimentada só por datasets rotulados e revistos.

### D5 — Verificação barata
Um prompt focado de um único campo ("o texto indica a data do incidente? cita o excerto") a um modelo barato. Só conta se citar um span que exista.

### D6 — Persistência e API
FastAPI com SQLite (demo) ou Postgres. Tabelas `arbitrations`, `candidates`, `field_decisions` e `reviews`. Autenticação com tokens demo com papéis `client` e `reviewer`.

### D7 — Experiência
A revisão humana é **simulada** a partir dos labels, com um custo por campo revisto configurável (por exemplo, 0,30 USD), para comparar o custo total incluindo humanos. Isto fica declarado no relatório.

### D8 — Documentação pedagógica
`docs/learn/arbitration/` tem: `01-porque-voto-nao-e-verdade`, `02-normalizacao`, `03-evidencia-e-offsets`, `04-calibracao-ece`, `05-abstencao-e-limiares`, `06-custo-vs-qualidade` e as perguntas de entrevista acrescentadas.

## Risks / Trade-offs

- [A procura de evidência falha com paráfrases ("no início do mês passado")] → Fica `evidence: none` e vai para revisão. A taxa é medida.
- [Calibração com poucos dados] → Split dedicado e intervalos reportados.
- [O custo da revisão humana simulado] → É um parâmetro explícito e há análise de sensibilidade.

## Migration Plan

Módulo novo. Não altera o comportamento existente do RegressionGuard.
