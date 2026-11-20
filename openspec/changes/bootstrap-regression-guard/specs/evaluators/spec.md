# Spec Delta

## Purpose

Pontuar cada saída de um sistema de IA com critérios explícitos, separando verificações exactas de comparações aproximadas e de juízos de um LLM.

## ADDED Requirements

### Requirement: Avaliadores determinísticos
O sistema SHALL incluir avaliadores com resultado passa/falha para: validade de JSON schema, ferramenta correcta chamada, ausência de acesso proibido, existência das citações nos chunks fornecidos e SQL apenas de leitura (análise AST).

#### Scenario: SQL de escrita
- **WHEN** a saída contém `UPDATE orders SET ...`
- **THEN** o avaliador `sql_read_only` falha com o motivo `write_statement`

#### Scenario: Citação inexistente
- **WHEN** a resposta cita um `chunk_id` que não estava no contexto
- **THEN** o avaliador `citations_exist` falha

### Requirement: Avaliadores semânticos com tolerância explícita
O sistema SHALL incluir exact match normalizado, F1 por campo/token e matching por similaridade com limiar configurável. Cada avaliador MUST declarar a normalização e a tolerância usadas.

#### Scenario: Normalização declarada
- **WHEN** o esperado é "Lisboa" e a saída é " lisboa "
- **THEN** o exact match normalizado passa e o resultado regista `normalization: [strip, casefold]`

### Requirement: Juiz LLM como sinal secundário
Um juiz LLM, quando activo, MUST usar uma rubrica fixa e versionada, e a sua concordância com labels humanos SHALL ser medida numa amostra de calibração. Os resultados do juiz NÃO SHALL decidir gates críticos.

#### Scenario: Juiz e gate crítico
- **WHEN** um caso crítico falha nos avaliadores determinísticos mas o juiz dá nota alta
- **THEN** o caso conta como falhado

### Requirement: Avaliadores testados
Cada avaliador SHALL ter testes unitários com casos positivos e negativos conhecidos.

#### Scenario: Teste do F1
- **WHEN** se corre a suite de testes dos avaliadores
- **THEN** o F1 de um exemplo calculado à mão coincide com o valor esperado
