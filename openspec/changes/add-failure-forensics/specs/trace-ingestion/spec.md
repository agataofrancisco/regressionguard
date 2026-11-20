# Spec Delta

## Purpose

Receber traces de aplicações de IA em formatos standard, normalizá-los e guardá-los sem segredos nem dados pessoais.

## ADDED Requirements

### Requirement: Importação OTLP e JSON
`POST /traces/import` SHALL aceitar traces OTLP (JSON) e um formato JSON simplificado documentado, e devolver os `trace_id` importados. Traces mal formados MUST ser rejeitados com a indicação do erro.

#### Scenario: Import OTLP
- **WHEN** se importa um ficheiro OTLP JSON com 2 traces
- **THEN** a resposta lista os 2 `trace_id` e os spans ficam consultáveis

#### Scenario: Trace incompleto
- **WHEN** um trace tem spans cujo pai não existe
- **THEN** é importado com a flag `incomplete_trace` e os spans órfãos ficam agrupados

### Requirement: Redacção antes de guardar
Atributos e payloads SHALL passar por redacção de segredos (chaves de API, tokens, passwords) e PII (emails, telefones, NIF/IBAN) **antes** de serem persistidos. Os valores originais NÃO SHALL ser guardados.

#### Scenario: Chave de API num atributo
- **WHEN** um span tem `http.request.header.authorization: "Bearer sk-..."`
- **THEN** o valor guardado é `[REDACTED:secret]`

### Requirement: Normalização semântica
Os spans SHALL ser normalizados para um modelo interno com tipo de etapa (`retrieve`, `rerank`, `generate`, `verify`, `tool_call`, `approval`, `route`, `fallback`), estado, duração e atributos relevantes, segundo um mapeamento configurável das convenções de nomes.

#### Scenario: Convenções diferentes
- **WHEN** dois sistemas nomeiam o retrieval como `retrieve` e `vector_search`
- **THEN** ambos são normalizados para o tipo `retrieve` pelo mapeamento

### Requirement: SDK de instrumentação de exemplo
O projecto SHALL incluir um SDK leve que cria spans com atributos padronizados para RAG, agentes e gateway, aplicado aos mini-alvos.

#### Scenario: Mini RAG instrumentado
- **WHEN** o mini RAG responde a uma pergunta
- **THEN** é produzido um trace com os spans `retrieve`, `generate` e `verify` e os atributos `retrieved_count` e `citations`
