# Spec Delta

## Purpose

Identificar tipos de falha em traces com regras auditáveis e apresentar diagnósticos que distinguem claramente o que foi observado do que é hipótese.

## ADDED Requirements

### Requirement: Taxonomia mínima
O sistema SHALL detectar pelo menos: `retrieval_miss`, `citation_unsupported`, `provider_timeout`, `rate_limit`, `schema_validation_failure`, `tool_permission_denied`, `stale_memory`, `prompt_injection_attempt`, `model_output_regression` e `budget_exceeded`.

#### Scenario: Timeout do provider
- **WHEN** um span `generate` termina com erro de timeout
- **THEN** é criado um diagnóstico `provider_timeout` ligado a esse span

### Requirement: Regras determinísticas com score de evidência
Cada tipo SHALL ser detectado por regras sobre atributos observáveis, com um score de evidência e um `confidence_method` que descreve a regra. Um LLM MAY resumir o trace, mas NÃO SHALL criar diagnósticos nem referir spans que não existem.

#### Scenario: Resumo por LLM
- **WHEN** o resumo gerado menciona um span inexistente
- **THEN** a menção é rejeitada pela validação e o resumo é marcado `invalid_reference`

### Requirement: Observação separada de hipótese
Cada diagnóstico MUST conter `observed_evidence` (factos do trace com referência a spans), `probable_hypothesis` (explicação provável, marcada como hipótese), `confidence_method`, `recommended_check` e `replay_id` quando reproduzível.

#### Scenario: Retrieval vazio seguido de resposta errada
- **WHEN** `retrieve` devolveu 0 chunks e a resposta foi gerada na mesma
- **THEN** a evidência observada é "retrieve.retrieved_count = 0 no span X" e a hipótese "resposta sem suporte por falha de retrieval", sem afirmar causalidade

### Requirement: Falhas aninhadas
Quando várias regras disparam no mesmo trace, o sistema SHALL ordená-las pela posição na árvore e pela dependência temporal e MUST indicar a falha mais a montante como candidata principal, sem descartar as restantes.

#### Scenario: Rate limit que causa fallback e timeout
- **WHEN** um trace contém `rate_limit`, depois `fallback` e depois `provider_timeout`
- **THEN** o incidente lista os três, com `rate_limit` como candidato principal
