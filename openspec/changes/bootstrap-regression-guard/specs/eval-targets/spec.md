# Spec Delta

## Purpose

Permitir avaliar qualquer sistema de IA através de uma interface comum de adaptador e fornecer dois sistemas-alvo de demonstração com configurações regredíveis.

## ADDED Requirements

### Requirement: Interface de adaptador
Um alvo SHALL ser registado por um adaptador que recebe o `input` de um caso e devolve uma saída estruturada (texto/JSON, citações, ferramentas chamadas, SQL, custo, latência, `trace_id`). Um adaptador MUST poder ser local (função Python) ou HTTP.

#### Scenario: Alvo HTTP
- **WHEN** se configura um alvo com URL e mapeamento de campos
- **THEN** a suite corre contra esse serviço sem alterar o código do harness

### Requirement: Mini app de extracção
O repositório SHALL incluir uma mini app que extrai JSON (`order_id`, `customer_tier`, `items`, `total`, `refund_requested`) de mensagens sintéticas de clientes de uma loja online fictícia, com prompt e schema configuráveis por versão.

#### Scenario: Versão regredida do schema
- **WHEN** a configuração `v2-broken` muda o nome de um campo
- **THEN** os casos de schema falham na avaliação

### Requirement: Mini RAG
O repositório SHALL incluir um mini RAG sobre uma FAQ sintética, com `top_k`, prompt e regras de citação configuráveis, e uma ferramenta SQL de leitura sobre uma tabela demo, para os casos de segurança.

#### Scenario: Retrieval reduzido
- **WHEN** a configuração reduz `top_k` de 5 para 1
- **THEN** os casos multi-hop passam a falhar

### Requirement: Modo mock determinístico
Os dois alvos SHALL ter um modo mock determinístico, que produz saídas reprodutíveis sem rede, para correr em CI.

#### Scenario: Reprodutibilidade
- **WHEN** a mesma suite mock é executada duas vezes
- **THEN** os resultados por caso são idênticos
