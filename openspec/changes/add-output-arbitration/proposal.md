# Proposal

## Why

Extrair dados de documentos com LLMs (datas, valores, matrículas, NIF) parece fácil até um erro num campo custar dinheiro. Pedir a dois ou três modelos e fazer "voto maioritário" é tentador, mas dois modelos podem cometer o mesmo erro, e o voto não sabe quando deve ficar calado. O ArbitrationLab acrescenta ao EvalSentinel uma camada de arbitragem cujo diferencial é **calibração + abstenção + evidências**. Cada valor tem de ser localizado no texto original. A confiança vem da fiabilidade histórica medida. Em caso de dúvida, o sistema abstém-se ou envia para revisão humana. O projecto mede também quando arbitrar **não** compensa.

Domínio fictício: participações de sinistro automóvel da **Seguros Horizonte Azul**. Os campos a extrair são `policy_number`, `incident_date`, `license_plate`, `claimed_amount`, `currency`, `third_party_involved` e `injuries_reported`. Todos os dados são sintéticos e não há PII real.

## What Changes

- Novo módulo `evalsentinel.arbitration`, com API FastAPI própria e que também funciona como avaliador opcional nas suites do RegressionGuard.
- Geração paralela de candidatos (2 ou 3 modelos ou variantes de prompt) com validação de schema e limites de tempo e custo (`max_spend`).
- Motor de arbitragem: normalização, verificação de evidência (span e offsets no texto original), acordo por campo, score de evidência e fiabilidade histórica por `(modelo, campo)`. O juiz LLM é opcional e só sugere.
- Decisão por campo: `accept`, `verify` (verificação barata extra se houver orçamento), `human_review` ou `abstain`.
- Revisão humana via API e painel de três colunas (candidatos, evidências, veredicto).
- Dataset sintético de 100 ou mais participações, com erros propositados e injecção no texto.
- Experiência comparativa: modelo barato só, modelo forte só, voto maioritário, arbitragem por evidência e arbitragem + revisão.
- Documentação de aprendizagem.

## Capabilities

### New Capabilities
- `candidate-generation`: geração paralela de candidatos estruturados com schema, timeout e orçamento.
- `evidence-arbitration`: normalização, verificação de evidência, acordo, fiabilidade calibrada e decisão por campo com abstenção.
- `human-review`: fila de revisão, decisões humanas e uso das decisões como labels.
- `arbitration-experiments`: dataset de participações, comparação de estratégias e relatório accuracy-vs-custo.

### Modified Capabilities
<!-- Nenhuma: reutiliza golden-datasets, evaluators e eval-runs sem alterar os seus requisitos. -->

## Impact

- **Código**: `src/evalsentinel/arbitration/`, `apps/arbitration_api/`, `datasets/claims/` e vistas no painel.
- **Dependências**: FastAPI, SQLAlchemy (SQLite em demo, Postgres opcional) e as já existentes.
- **Depende de** `bootstrap-regression-guard` (datasets, runs e store).
