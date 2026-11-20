# Spec Delta

## Purpose

Agrupar diagnósticos em incidentes navegáveis, permitir reproduzi-los em segurança e aprender com o feedback de quem os investiga.

## ADDED Requirements

### Requirement: Incidentes consultáveis
`GET /incidents` SHALL listar os incidentes com filtros por tipo, severidade, data e serviço. `GET /incidents/{id}` SHALL devolver a timeline, a árvore de spans, os diagnósticos e a versão.

#### Scenario: Filtrar por tipo
- **WHEN** se filtra por `citation_unsupported` na última semana
- **THEN** só aparecem incidentes desse tipo nesse período

### Requirement: Versionamento e feedback
Cada alteração de diagnóstico (nova regra, reclassificação) SHALL criar uma nova versão do incidente. `POST /incidents/{id}/feedback` SHALL permitir marcar falso positivo ou confirmar, com comentário e autor.

#### Scenario: Falso positivo
- **WHEN** um investigador marca um diagnóstico como falso positivo
- **THEN** o diagnóstico fica `dismissed`, o feedback entra nas métricas de FP e a versão anterior mantém-se consultável

### Requirement: Replay em sandbox
`POST /incidents/{id}/replay` SHALL reexecutar o input **sintético ou redigido** do incidente contra o alvo em modo sandbox, sem ferramentas mutáveis reais, e ligar o novo trace ao incidente.

#### Scenario: Replay com ferramenta mutável
- **WHEN** o trace original incluía uma acção mutável
- **THEN** no replay essa ferramenta é substituída por um stub e nenhum efeito real acontece

#### Scenario: Input não reproduzível
- **WHEN** o input foi redigido e não é possível reproduzi-lo
- **THEN** o replay é recusado com `not_replayable` e o motivo

### Requirement: Comparação e relatório
O sistema SHALL permitir comparar lado a lado uma execução boa e uma má do mesmo tipo e gerar um relatório Markdown do incidente.

#### Scenario: Relatório
- **WHEN** se pede o relatório de um incidente
- **THEN** o Markdown contém a evidência, as hipóteses marcadas como tal, os checks recomendados e os links para os spans
