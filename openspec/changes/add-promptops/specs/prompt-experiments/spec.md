# Spec Delta

## Purpose

Comparar versões de prompts de forma justa, offline sobre dados congelados e online com utilizadores reais, sem conclusões estatísticas não suportadas.

## ADDED Requirements

### Requirement: Experiência offline congelada
`POST /experiments` com tipo `offline` e `POST /experiments/{id}/run` SHALL executar todas as versões escolhidas sobre a mesma versão de dataset (≥80 exemplos), com o mesmo modelo, temperatura e settings, e guardar os resultados por versão.

#### Scenario: Settings diferentes
- **WHEN** as versões comparadas usam temperaturas diferentes sem `allow_settings_diff`
- **THEN** a experiência é recusada com `unfair_comparison`

### Requirement: Atribuição estável no A/B online
Numa experiência `online`, a variante de um utilizador SHALL ser determinada por `hash(experiment_id, user_id)` com as percentagens configuradas, e MUST permanecer a mesma durante toda a experiência, mesmo que as percentagens sejam alteradas.

#### Scenario: Utilizador volta mais tarde
- **WHEN** o mesmo utilizador é atribuído duas vezes na mesma experiência
- **THEN** recebe sempre a mesma variante

#### Scenario: Distribuição
- **WHEN** 10 000 utilizadores sintéticos são atribuídos com 10/90
- **THEN** a proporção de A fica dentro do intervalo de tolerância estatística de 10%

### Requirement: Exposições sem duplicados
`POST /experiments/{id}/exposure` SHALL registar a exposição e o resultado com uma chave idempotente. Exposições repetidas NÃO SHALL contar duas vezes.

#### Scenario: Exposição repetida
- **WHEN** a mesma exposição é enviada duas vezes
- **THEN** é contada uma vez

### Requirement: Consentimento para feedback
O feedback dos utilizadores só SHALL ser recolhido quando há consentimento registado. Sem consentimento, só as métricas técnicas (latência, custo, erro) são guardadas.

#### Scenario: Sem consentimento
- **WHEN** um utilizador sem consentimento envia feedback
- **THEN** o feedback não é guardado e a exposição regista `feedback: not_consented`

### Requirement: Resultados honestos
`GET /experiments/{id}/results` SHALL mostrar as métricas por variante com intervalos de confiança e MUST mostrar `insufficient_sample_size` em vez de declarar um vencedor quando a amostra ou o método não o suportam.

#### Scenario: Poucos utilizadores
- **WHEN** a variante B tem 40 exposições
- **THEN** os resultados mostram os intervalos e `insufficient_sample_size`, sem vencedor

### Requirement: Kill switch
`POST /experiments/{id}/stop` SHALL parar imediatamente a experiência e enviar todo o tráfego para a variante de controlo.

#### Scenario: Parar experiência
- **WHEN** um maintainer pára a experiência
- **THEN** as resoluções seguintes devolvem só o controlo e o evento fica auditado
