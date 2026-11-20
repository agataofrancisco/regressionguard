# Spec Delta

## Purpose

Obter várias extracções independentes do mesmo documento, de forma paralela, validada e dentro de limites de tempo e custo.

## ADDED Requirements

### Requirement: Pedido de arbitragem
`POST /arbitrations` SHALL aceitar `task_id`, o texto de input, o schema JSON de saída, a política (candidatos a usar, limiares) e `max_spend`, e devolver um `arbitration_id`.

#### Scenario: Pedido válido
- **WHEN** um cliente autenticado envia o texto de uma participação e o schema de sinistro
- **THEN** recebe `201` com `arbitration_id` e o estado inicial

#### Scenario: Schema inválido
- **WHEN** o schema enviado não é JSON Schema válido
- **THEN** recebe `422` e nenhum modelo é chamado

### Requirement: Candidatos paralelos com validação
O sistema SHALL gerar candidatos em paralelo a partir de 2 ou 3 modelos ou variantes de prompt. Cada candidato MUST ser validado contra o schema. Um candidato inválido ou que exceda o timeout SHALL ficar marcado e não conta para o acordo.

#### Scenario: Um candidato excede o timeout
- **WHEN** um dos três modelos não responde dentro do limite
- **THEN** a arbitragem continua com os dois restantes e o candidato fica `timed_out`

### Requirement: Orçamento por arbitragem
O custo acumulado (candidatos + verificações + juiz) NÃO SHALL exceder `max_spend`. Quando o orçamento não chega para um passo, esse passo MUST ser omitido e o motivo registado.

#### Scenario: Sem orçamento para o terceiro candidato
- **WHEN** os dois primeiros candidatos consomem quase todo o `max_spend`
- **THEN** o terceiro não é pedido e o registo indica `skipped: budget`

### Requirement: Provider mock
O sistema SHALL incluir candidatos mock determinísticos com perfis de erro configuráveis (por exemplo, trocar dia e mês, omitir campo, repetir o mesmo erro em dois modelos), para CI sem custo.

#### Scenario: Erro correlacionado simulado
- **WHEN** o perfil `correlated_date_error` está activo
- **THEN** dois candidatos devolvem a mesma data errada
