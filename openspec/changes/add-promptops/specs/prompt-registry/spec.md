# Spec Delta

## Purpose

Guardar prompts como artefactos versionados e imutáveis, com variáveis tipadas e aliases que indicam qual versão está em cada ambiente.

## ADDED Requirements

### Requirement: Versões imutáveis
`POST /prompts/{id}/versions` SHALL criar uma nova versão numerada com o template, as variáveis tipadas, o modelo e as settings. Uma versão criada NÃO SHALL ser alterável. Qualquer mudança MUST criar uma nova versão.

#### Scenario: Tentativa de alterar versão
- **WHEN** um cliente tenta modificar a versão 3 de um prompt
- **THEN** recebe `409` com `code: "version_immutable"`

### Requirement: Variáveis tipadas
Cada versão SHALL declarar as suas variáveis com tipo e obrigatoriedade. Renderizar um prompt com variáveis em falta ou de tipo errado MUST falhar com um erro explícito.

#### Scenario: Variável em falta
- **WHEN** se resolve uma versão que exige `customer_message` sem a fornecer
- **THEN** a renderização falha com `missing_variable: customer_message`

### Requirement: Aliases e resolução
`PUT /prompts/{id}/aliases/{name}` SHALL apontar um alias para uma versão e `GET /prompts/{id}/resolve?alias=production` SHALL devolver a versão actual. Mudanças concorrentes de alias MUST ser serializadas, sem estados intermédios.

#### Scenario: Duas promoções simultâneas
- **WHEN** dois pedidos mudam o alias `production` ao mesmo tempo
- **THEN** só um prevalece, o outro recebe `409` e a auditoria regista ambos

### Requirement: Tenants e acesso
Prompts, versões e datasets SHALL ter dono e tenant. Utilizadores NÃO SHALL ler nem alterar prompts de outro tenant, e só papéis `maintainer` podem mudar aliases.

#### Scenario: Leitura cross-tenant
- **WHEN** um utilizador de outro tenant resolve um prompt
- **THEN** recebe `404`

### Requirement: Auditoria e exportação
Cada criação, alteração de alias e rollback MUST gerar um `AuditEvent` imutável. O sistema SHALL exportar prompts e versões em YAML ou JSON.

#### Scenario: Exportar
- **WHEN** se exporta um prompt
- **THEN** o YAML contém todas as versões, variáveis, aliases actuais e hashes

### Requirement: Prompts com PII
Ao criar uma versão, o sistema SHALL detectar PII óbvia no template (emails, telefones, NIF) e MUST bloquear a criação, salvo override justificado e auditado.

#### Scenario: Email no template
- **WHEN** um template contém um email real
- **THEN** a criação é bloqueada com `pii_detected`
