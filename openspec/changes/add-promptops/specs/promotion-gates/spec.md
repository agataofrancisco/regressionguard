# Spec Delta

## Purpose

Impedir que uma versão de prompt pior chegue a produção e permitir voltar atrás instantaneamente, tanto pela API como pelo fluxo de pull requests.

## ADDED Requirements

### Requirement: Promoção condicionada a gates
Mudar o alias `production` para uma nova versão SHALL exigir uma avaliação offline dessa versão contra a versão actual, com os gates de não-regressão configurados. Se um gate crítico falhar, a promoção MUST ser recusada.

#### Scenario: Promoção bloqueada
- **WHEN** a nova versão quebra o schema de saída em casos críticos
- **THEN** a promoção é recusada com `gate_failed` e a lista de casos regredidos

#### Scenario: Promoção aceite
- **WHEN** a nova versão passa todos os gates críticos
- **THEN** o alias aponta para a nova versão e a auditoria guarda o `run_id` da avaliação

### Requirement: Rollback imediato
O sistema SHALL permitir repor o alias para qualquer versão anterior com um único pedido, sem nova avaliação, com registo de auditoria.

#### Scenario: Rollback
- **WHEN** um maintainer faz rollback de `production` para a versão 4
- **THEN** a resolução seguinte devolve a versão 4

### Requirement: Integração com pull requests
Uma GitHub Action SHALL detectar alterações a ficheiros de prompt num PR, criar versões candidatas, correr a avaliação offline em mock e falhar o check se algum gate crítico falhar.

#### Scenario: PR com prompt pior
- **WHEN** um PR altera um prompt de forma que remove as citações
- **THEN** o check falha e o resumo do PR mostra o gate e os exemplos

#### Scenario: PR com prompt melhor
- **WHEN** um PR altera um prompt e todos os gates passam
- **THEN** o check passa e o resumo mostra as métricas comparadas
