# Spec Delta

## Purpose

Tornar os resultados das avaliações visíveis e accionáveis: na CLI, em relatórios partilháveis, no CI dos pull requests e num painel.

## ADDED Requirements

### Requirement: Relatórios
`ai-eval report --run <id> --html` SHALL gerar um relatório HTML autónomo e um JSON com o resumo, as métricas por segmento, os casos falhados, os custos e as ligações a `trace_id`.

#### Scenario: Relatório HTML
- **WHEN** se gera o relatório de uma run
- **THEN** o ficheiro abre sem servidor e mostra o resumo, os segmentos e os casos falhados

### Requirement: Integração em CI
O repositório SHALL incluir uma GitHub Action que, em cada pull request, corre a suite smoke em modo mock, compara com o baseline do ramo principal e publica um resumo. Execuções live MUST correr apenas em job manual, com segredo e `--max-usd`.

#### Scenario: PR com regressão
- **WHEN** um PR introduz uma das regressões do laboratório
- **THEN** o job falha e o resumo do PR mostra o gate falhado

#### Scenario: PR de fork
- **WHEN** um PR vem de um fork
- **THEN** só corre o modo mock, sem acesso a segredos

### Requirement: Painel de resultados
O sistema SHALL oferecer um painel com a lista de runs e versões, a evolução das métricas, os diffs entre runs, os exemplos quebrados, a pontuação por segmento e a recomendação de rollback.

#### Scenario: Navegar regressões
- **WHEN** um utilizador abre a comparação de duas runs
- **THEN** vê as métricas lado a lado e pode abrir cada caso regredido

### Requirement: Integrações externas opcionais
O sistema MAY exportar runs para Langfuse ou Phoenix, ou importar resultados do promptfoo. Estas integrações NÃO SHALL ser necessárias para o funcionamento base.

#### Scenario: Sem integrações
- **WHEN** nenhuma integração está configurada
- **THEN** todas as funcionalidades base funcionam
