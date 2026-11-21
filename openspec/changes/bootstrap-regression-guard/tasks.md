# Tasks

## 1. Fundações

- [x] 1.1 Criar `src/regressionguard/{datasets,targets,evaluators,runner,store,compare,report,cli}`, `targets/`, `datasets/`, `reports/` e `docs/learn/`; verificar com `git status`
- [x] 1.2 Confirmar e fixar versões (Pydantic v2, Typer, DuckDB, Jinja2, numpy, scipy, jsonschema, sqlglot, httpx, pytest, Ruff) em `pyproject.toml` com o entry point `ai-eval`; verificar que `ai-eval --help` funciona após `pip install -e .`
- [x] 1.3 Escrever `docs/learn/00-visao-geral.md` e `01-porque-avaliar-llms-e-diferente.md`; verificar que o diagrama corresponde aos módulos

## 2. Datasets e alvos

- [x] 2.1 Implementar o manifesto, o schema de caso, a validação (linha exacta, ids duplicados) e o hash de versão; verificar com testes
- [x] 2.2 Implementar a interface de adaptador (local e HTTP) e os mini-alvos `extraction` e `minirag` com mock determinístico e as configurações `v1` e regredidas; verificar com teste de reprodutibilidade
- [x] 2.3 Criar >80 casos rotulados (os dois alvos, categorias de segurança incluídas) e `ai-eval datasets stats/validate`; verificar a contagem e a distribuição
- [x] 2.4 Escrever `docs/learn/02-goldens-e-labels.md` e `CONTRIBUTING-goldens.md`; verificar seguindo o guia para adicionar um caso

## 3. Avaliadores

- [x] 3.1 Implementar os avaliadores determinísticos (schema, ferramenta, acesso proibido, citações, `sql_read_only` com sqlglot); verificar com testes positivos e negativos
- [x] 3.2 Implementar os avaliadores semânticos (exact match normalizado, F1, similaridade com limiar) com normalização declarada; verificar com testes de exemplos calculados à mão
- [x] 3.3 Implementar o juiz LLM opcional com rubrica versionada e a calibração (kappa); verificar com teste que o juiz não altera gates críticos
- [x] 3.4 Escrever `docs/learn/03-avaliadores-deterministicos.md`, `04-avaliadores-semanticos.md` e `05-llm-as-judge-e-calibracao.md`; verificar os exemplos com testes

## 4. Runs e armazenamento

- [x] 4.1 Implementar o store DuckDB (runs, case_results, evaluator_results) e o JSON de auditoria; verificar com teste de escrita e leitura
- [x] 4.2 Implementar `ai-eval run` (mock/live, `--max-usd` obrigatório em live, paragem por tecto, `--repeats`, seed, flaky); verificar com testes de live sem tecto, tecto atingido e caso flaky
- [x] 4.3 Escrever `docs/learn/06-aleatoriedade-e-repeticoes.md`; verificar com uma run real em mock

## 5. Comparação e gates

- [x] 5.1 Implementar a comparação emparelhada com bootstrap IC 95%, McNemar e `insufficient_sample_size`; verificar com testes sobre dados sintéticos com diferença conhecida
- [x] 5.2 Implementar `gates.yaml`, a avaliação crítico/aviso, os exit codes, a secção `regressions` e a recomendação de rollback sem acção; verificar com testes de gate crítico (exit 1) e aviso (exit 0)
- [x] 5.3 Executar o laboratório das 4 regressões e confirmar a detecção de cada uma, registando os falsos positivos; verificar com `pytest -m lab`
- [x] 5.4 Escrever `docs/learn/07-comparacao-emparelhada-bootstrap-mcnemar.md` e `09-laboratorio-de-regressoes.md` com os resultados obtidos; verificar que os números vêm das runs

## 6. Relatórios, CI e painel

- [ ] 6.1 Implementar `ai-eval report --html/--json` com template Jinja2 autónomo; verificar que abre sem servidor
- [ ] 6.2 Criar `.github/workflows/eval.yml` (mock no PR com baseline artifact, live manual com `--max-usd`); verificar a validade e simular localmente os comandos
- [ ] 6.3 Criar o índice de runs e o painel opcional (Streamlit sobre DuckDB) com diffs e casos regredidos; verificar no browser
- [ ] 6.4 Documentar as integrações opcionais (promptfoo, Langfuse, Phoenix) e o que cada uma faz melhor; verificar que o funcionamento base não depende delas
- [ ] 6.5 Escrever `docs/learn/08-gates-e-ci.md`; verificar com um PR de exemplo pass/fail descrito com output real

## 7. Entrega

- [ ] 7.1 Escrever `README.md`, `docs/architecture.md`, `docs/decisions.md` e `docs/case-study.md` (a regressão real do laboratório); verificar que os comandos correm
- [ ] 7.2 Escrever `docs/learn/10-perguntas-de-entrevista.md` (≥25); verificar a consistência com o código
- [ ] 7.3 Revisão independente (segredos no CI, custo live, honestidade estatística); verificar que os achados estão resolvidos ou documentados

## Workflow follow-up

- Adaptadores para o GroundVault e o QueryShield quando existirem.
- Publicar uma tag de versão (por exemplo `v0.1.0`) para o PromptOps fixar a dependência.
- Arquivar a change após revisão.
