# Spec Delta

## Purpose

Executar suites de avaliação de forma reproduzível, controlando custo e aleatoriedade, e guardar o histórico completo de cada execução.

## ADDED Requirements

### Requirement: Modos mock e live
`ai-eval run --suite <nome> --mode mock|live` SHALL executar a suite contra o alvo. O modo `live` MUST exigir `--max-usd` e parar antes de exceder esse valor.

#### Scenario: Live sem tecto
- **WHEN** se executa `ai-eval run --suite full --mode live` sem `--max-usd`
- **THEN** a CLI recusa com erro e não faz chamadas

#### Scenario: Tecto atingido
- **WHEN** o custo acumulado chega ao `--max-usd`
- **THEN** a run pára, fica marcada `incomplete: budget_reached` e não é usada para gates

### Requirement: Repetições e dispersão
O sistema SHALL suportar `--repeats N`, usar seed quando o provider a suporta e registar por caso a média, o desvio e a taxa de sucesso entre repetições.

#### Scenario: Caso instável
- **WHEN** um caso passa em 3 de 5 repetições
- **THEN** o resultado regista `pass_rate: 0.6` e o caso é marcado `flaky`

### Requirement: Registo completo da run
Cada run MUST guardar `run_id`, data, commit, versão do dataset, configuração do alvo (modelo, prompt, parâmetros), modo, repetições, resultado por caso e avaliador, custo, latência e `trace_id` quando disponível.

#### Scenario: Reprodutibilidade
- **WHEN** se consulta uma run antiga
- **THEN** é possível ver exactamente com que configuração e versão do dataset foi feita

### Requirement: Métricas operacionais
Cada run SHALL reportar o custo por caso, a latência p50/p95, a taxa de abstenção, a taxa de erro e as violações de segurança, por categoria.

#### Scenario: Resumo da run
- **WHEN** a run termina
- **THEN** o resumo mostra estas métricas por categoria e no total
