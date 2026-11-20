# Proposal

## Why

Em software normal, um teste que passa hoje passa amanhã. Em aplicações com LLMs, uma mudança num prompt, num modelo, no `top_k` do retrieval ou numa configuração pode degradar a qualidade em silêncio, e as saídas variam de chamada para chamada. O **RegressionGuard** é um harness que fixa datasets golden, guarda baselines por versão e bloqueia PRs que introduzem regressões, tratando a aleatoriedade com repetições e intervalos de confiança em vez de uma única chamada.

O RegressionGuard avalia sistemas-alvo. Nesta change são dois mini-alvos incluídos no repositório: uma **mini app de extracção estruturada** (dados de encomendas de uma loja online fictícia) e um **mini RAG** (FAQ de um serviço fictício). Mais tarde também pode avaliar os outros projectos do portefólio (GroundVault, QueryShield) através de adaptadores.

## What Changes

- Projecto novo em `projects/regressionguard` com o pacote Python `regressionguard` (também usado como biblioteca pelo projecto PromptOps) e a CLI `ai-eval`.
- Datasets golden versionados em JSONL, com labels rastreáveis e validação de schema.
- Avaliadores determinísticos (JSON schema, ferramenta correcta, sem acessos proibidos, citações existentes, SQL só de leitura), semânticos (exact match, F1, matching com tolerâncias) e um juiz LLM opcional apenas como sinal secundário calibrado.
- Execução estocástica com N repetições, seed quando suportada, dispersão e comparação emparelhada baseline vs candidato com intervalo de confiança.
- Histórico de runs em DuckDB, gates críticos (exit ≠ 0) e não críticos (warnings), relatórios HTML/JSON e uma recomendação de rollback **sem** rollback automático.
- GitHub Action: mocks determinísticos nos PRs e providers reais só num job manual com tecto de custo.
- Laboratório com 4 regressões controladas, que têm de ser detectadas.
- Documentação de aprendizagem em `docs/learn/`.

## Capabilities

### New Capabilities
- `golden-datasets`: formato, versionamento, validação e guia de contribuição de casos golden.
- `evaluators`: avaliadores determinísticos, semânticos e juiz LLM calibrado.
- `eval-runs`: execução de suites em modo mock ou live, repetições, custo máximo e histórico.
- `regression-comparison`: comparação baseline vs candidato, estatística, gates e recomendação de rollback.
- `eval-reporting`: CLI, relatórios HTML/JSON, integração CI e painel de resultados.
- `eval-targets`: interface de adaptadores para sistemas avaliados e os dois mini-alvos de demonstração.

### Modified Capabilities
<!-- Nenhuma: projecto novo. -->

## Impact

- **Código novo**: `src/regressionguard/`, `targets/`, `datasets/`, `.github/workflows/`, `reports/` e `docs/`.
- **Dependências** (confirmar versões): Pydantic v2, Typer, DuckDB, Jinja2, numpy/scipy (bootstrap e testes), jsonschema, sqlglot, httpx, pytest e Ruff. Integrações opcionais com promptfoo, Langfuse e Phoenix, apenas documentadas e sem reimplementar o que oferecem.
- **Não depende** da plataforma OpenAI Evals antiga (descontinuada).
- **API pública estável** (`regressionguard.compare`, avaliadores e gates) com versionamento semântico, porque o PromptOps a importa como dependência.
