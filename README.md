# RegressionGuard

Harness de avaliação e deteccao de regressões para sistemas com LLMs. Fixa datasets golden, mede
um sistema-alvo com repetições, compara um candidato contra um baseline de forma emparelhada e
aplica gates: gates críticos fazem o comando terminar com código 1; avisos apenas informam.
A recomendação de rollback é gravada, nunca executada.

Pacote Python `regressionguard` e CLI `ai-eval`. Também é usado como biblioteca pelo PromptOps.

## Instalação

Requer Python 3.12. Não requer Docker, GPU nem base de dados externa.

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Windows (Git Bash: .venv/Scripts/...)
# opcional, painel Streamlit:
.venv/Scripts/python.exe -m pip install -e ".[dashboard]"
```

Versões fixadas em `pyproject.toml` (Pydantic, Typer, DuckDB, Jinja2, numpy, scipy, jsonschema, sqlglot,
httpx, PyYAML; pytest e Ruff em `dev`; Streamlit em `dashboard`).

## Uso rápido (mock, sem rede e sem chaves)

```bash
ai-eval datasets validate              # valida os datasets das suites
ai-eval datasets stats                 # 90 casos: alvo, categoria, severidade
ai-eval run --suite full --config-set v1 --mode mock --tag baseline
ai-eval run --suite full --config-set no-citations --mode mock
ai-eval compare --baseline <id-1> --candidate <id-2> --html   # exit 1: gate critico falhado
ai-eval index                          # reports/index.html com runs e comparações
ai-eval runs                           # lista as runs guardadas
```

Conjuntos de configuração disponíveis em `targets/sets/`: `v1` (baseline) e as quatro regressões do
laboratório (`no-citations`, `unauthorized-select`, `schema-change`, `k1`).

Saídas:
- `regressionguard.duckdb` (histórico: `runs`, `case_results`, `evaluator_results`; ignorado pelo git);
- `reports/runs/<run_id>.json` (auditoria completa de cada run);
- `reports/html/`, `reports/comparisons/`, `reports/index.html` (relatórios HTML autónomos, sem servidor).

### Códigos de saída

| Código | Significado |
|---|---|
| 0 | Aprovado (com ou sem avisos) |
| 1 | Gate crítico falhado (`compare`) ou dataset inválido (`datasets validate`) |
| 2 | Uso inválido, configuração errada, ou comparação recusada (`dataset_version_mismatch`, `run_incomplete`, `mode_mismatch`) |

## Modo live (LLM real)

`--mode live` exige `--max-usd`. Sem o tecto a CLI recusa antes de qualquer chamada. A chave é lida de
uma variável de ambiente (`REGRESSIONGUARD_API_KEY` por omissão), nunca de ficheiros do repositório.
O teto é a priori: antes de cada chamada soma-se o limite superior do custo (pior caso, com `params.live.max_tokens`). Uma chamada que excederia o teto não é feita. Os preços (`params.live.price_input_per_1k` e `price_output_per_1k`) e `max_tokens` são obrigatórios na configuração do
alvo: sem eles o custo não é medido. Os valores em `targets/*/configs/*.yaml` estão a `null` com
`TODO`, por isso um run live falha até serem preenchidos.

**Não foi executado nenhum run live neste repositório.** Não há chaves disponíveis. O modo live está
implementado e testado com um transporte falso (`httpx.MockTransport`).

O job manual `workflow_dispatch` de `.github/workflows/eval.yml` corre o modo live com `max_usd` e o
segredo `REGRESSIONGUARD_API_KEY` configurado pelo dono do repositório.

## Biblioteca (API pública)

```python
import regressionguard as rg

gates = rg.load_gates("config/gates.yaml")
report = rg.compare(baseline_run, candidate_run, gates)  # RunRecord -> ComparisonReport
report.exit_code  # 0 ou 1
report.regressions  # casos que passavam e deixaram de passar, com as duas saídas
report.recommendation  # {"action": "rollback", "applied": False, ...} quando há gate crítico
```

Símbolos estáveis: `compare`, `ComparisonReport`, `ComparisonError`, `GatesConfig`, `GateSpec`,
`load_gates`, `register`, `EvalContext`, `EvalResult`, `get_evaluator`, `evaluator_names`,
`load_dataset`, `Dataset`, `Case`, `DatasetError`, `RunRecord`. Versionamento semântico; o PromptOps fixa a versão.

## Datasets e alvos

- Datasets JSONL em `datasets/<alvo>/golden.jsonl`: manifesto na primeira linha, depois um caso por linha.
  Regras de contribuição em `CONTRIBUTING-goldens.md`.
- Alvos de demonstração: mini app de extração (`targets/extraction/`) e mini RAG sobre uma FAQ fictícia
  (`targets/minirag/`). Ambos têm modo mock determinista.
- Adaptador HTTP para avaliar um serviço externo: `provider: http` com `params.url` e `field_map` (ver
  `src/regressionguard/targets/http.py`).

## Painel opcional

```bash
streamlit run src/regressionguard/dashboard/app.py
```

Lista as runs, compara quaisquer duas e mostra gates, segmentos e casos regredidos com as duas saídas.
Só lê o DuckDB e não executa rollbacks.

## Integrações opcionais

Estão **apenas documentadas** (sem código de integração nesta change): promptfoo, Langfuse e Phoenix.
O funcionamento base não depende delas. Ver `docs/integrations.md`.

## CI

`.github/workflows/eval.yml`:
- **pull_request**: lint, testes e suite `smoke` em mock; compara com o artefacto `baseline` do `main`
  e publica o resumo. PRs de forks não têm segredos e não usam nenhum.
- **push para main**: recria o artefacto `baseline`.
- **workflow_dispatch**: run live manual com `max_usd`.

O workflow não foi executado no GitHub (sem acesso). Foi validado como YAML e os comandos foram simulados
localmente em duas cópias do repositório (baseline "main" e candidato "PR").

## Documentação

- `docs/learn/` — material de estudo em português de Portugal, com saídas reais e perguntas de entrevista.
- `docs/architecture.md`, `docs/decisions.md`, `docs/case-study.md`.
- `openspec/changes/bootstrap-regression-guard/` — proposta, design, especificações e tarefas.

## Desenvolvimento

```bash
ruff check . && ruff format --check .
pytest -q            # testes unitários e de integração (mock)
pytest -m lab        # laboratório das 4 regressões
```

Estado atual: ver `openspec/changes/bootstrap-regression-guard/tasks.md`. Os números de avaliação deste
repositório são de **modo mock** e não medem um modelo real.
