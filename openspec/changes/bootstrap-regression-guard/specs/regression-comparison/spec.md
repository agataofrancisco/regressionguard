# Spec Delta

## Purpose

Decidir de forma estatisticamente honesta se um candidato é pior do que o baseline, aplicando gates configuráveis sem tomar acções automáticas irreversíveis.

## ADDED Requirements

### Requirement: Comparação emparelhada
`ai-eval compare --baseline <id> --candidate <id>` SHALL comparar as runs caso a caso (pares sobre os mesmos `id`) e reportar a diferença por métrica e por categoria, com intervalo de confiança quando o número de casos e repetições o permite.

#### Scenario: Diferença com intervalo
- **WHEN** baseline e candidato têm 80 casos e 3 repetições
- **THEN** o relatório mostra a diferença da taxa de sucesso com intervalo de confiança a 95% e o método usado

#### Scenario: Amostra pequena
- **WHEN** a comparação tem menos casos do que o mínimo configurado
- **THEN** o resultado é marcado `insufficient_sample_size` e não é apresentado como conclusivo

### Requirement: Gates críticos e não críticos
Os limiares SHALL ser definidos em configuração versionada. Uma falha de gate crítico (por exemplo, qualquer violação de segurança nova ou uma queda acima do limiar em casos `critical`) MUST fazer a CLI terminar com código diferente de zero. Gates não críticos SHALL produzir avisos com evidências.

#### Scenario: Gate crítico
- **WHEN** o candidato introduz um caso novo de SQL de escrita
- **THEN** `ai-eval compare` termina com exit code 1 e lista o caso

#### Scenario: Gate não crítico
- **WHEN** a latência p95 sobe 15% com o limiar de aviso a 10%
- **THEN** a CLI emite um aviso e termina com código 0

### Requirement: Exemplos quebrados
A comparação SHALL listar os casos que passavam no baseline e falham no candidato, com input, saída anterior, saída nova e avaliador que falhou.

#### Scenario: Caso quebrado
- **WHEN** um caso deixa de passar
- **THEN** aparece na secção `regressions` com as duas saídas lado a lado

### Requirement: Rollback só recomendado
O sistema SHALL emitir uma recomendação de rollback quando há gates críticos falhados e NÃO SHALL executar rollback automaticamente.

#### Scenario: Recomendação
- **WHEN** um gate crítico falha
- **THEN** o relatório inclui `recommendation: rollback` e a configuração do baseline a repor, sem a aplicar

### Requirement: Detecção das regressões do laboratório
O laboratório SHALL incluir 4 regressões controladas (remover citações, fazer um SELECT não autorizado, alterar o schema de saída, reduzir o `k` do retrieval) e o sistema MUST detectar cada uma.

#### Scenario: Remoção de citações
- **WHEN** o candidato do mini RAG deixa de citar fontes
- **THEN** a comparação falha o gate crítico de citações
