# Spec Delta

## Purpose

Encaminhar os campos duvidosos para um revisor humano com toda a informação necessária e usar as decisões como dados rotulados.

## ADDED Requirements

### Requirement: Consulta do resultado e dos candidatos
`GET /arbitrations/{id}` SHALL devolver o veredicto por campo (valor, decisão, confiança, motivo) e `GET /arbitrations/{id}/candidates` SHALL devolver os candidatos com as evidências, o custo e a latência.

#### Scenario: Consulta com abstenção
- **WHEN** um campo foi `abstain`
- **THEN** a resposta inclui o motivo da abstenção e os valores candidatos considerados

### Requirement: Decisão humana
`POST /arbitrations/{id}/human-review` SHALL permitir a um revisor autorizado confirmar, corrigir ou marcar como ilegível cada campo pendente. A decisão MUST ficar auditada (quem, quando, valor anterior e novo).

#### Scenario: Correcção de data
- **WHEN** um revisor corrige `incident_date` para "2026-02-03"
- **THEN** o campo fica `accepted_by_human` e a auditoria regista a alteração

#### Scenario: Utilizador sem papel de revisor
- **WHEN** um utilizador sem papel `reviewer` envia uma decisão
- **THEN** recebe `403`

### Requirement: Decisões como labels
As decisões humanas SHALL poder ser exportadas como casos rotulados para actualizar a fiabilidade histórica, e só depois de uma revisão do dataset, nunca automaticamente.

#### Scenario: Exportação
- **WHEN** se exportam as revisões da semana
- **THEN** é gerado um ficheiro JSONL compatível com os datasets golden, marcado `source: human_review`

### Requirement: Painel de três colunas
O painel SHALL mostrar os candidatos, as evidências destacadas no texto e o veredicto, com as diferenças por campo, o motivo de abstenção, o custo incremental e a latência.

#### Scenario: Ver evidência
- **WHEN** o revisor clica num campo
- **THEN** o span correspondente é destacado no texto original
