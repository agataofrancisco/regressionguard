# Spec Delta

## Purpose

Medir a qualidade do diagnóstico com falhas injectadas de forma controlada, sem extrapolar ganhos de MTTR empresariais que não foram medidos.

## ADDED Requirements

### Requirement: Suite de fault injection
O projecto SHALL incluir pelo menos 8 cenários de falha injectada nos mini-alvos, cada um com um label golden do tipo e do span onde a falha realmente ocorreu. Inclui traces incompletos, dados redigidos, mensagens adversariais e falhas aninhadas.

#### Scenario: Gerar traces de teste
- **WHEN** a suite de injecção corre
- **THEN** produz traces e um ficheiro de labels com tipo e span esperado por cenário

### Requirement: Métricas de diagnóstico
O runner SHALL medir a precisão e o recall por tipo de falha, a taxa de falsos positivos, a percentagem de incidentes reproduzidos e a exactidão da localização (o span principal coincide com o label).

#### Scenario: Relatório de diagnóstico
- **WHEN** a avaliação termina
- **THEN** o relatório mostra estas métricas por tipo, com data, commit e versão das regras

### Requirement: Tempo de localização controlado
O sistema MAY medir o tempo até localizar a falha em tarefas de teste controladas e MUST apresentá-lo como medição de laboratório, NÃO SHALL apresentá-lo como redução de MTTR em produção.

#### Scenario: Linguagem do relatório
- **WHEN** o relatório inclui tempos de localização
- **THEN** são rotulados "tarefas controladas de laboratório"

### Requirement: Exemplos correctos e incorrectos
A documentação SHALL incluir exemplos reais (da suite) de diagnósticos correctos e incorrectos, com a explicação do erro.

#### Scenario: Diagnóstico errado documentado
- **WHEN** uma regra classifica mal um cenário
- **THEN** o caso aparece na secção de limitações com a causa
