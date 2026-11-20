# Tasks

## 1. Ingestão e instrumentação

- [ ] 1.1 Implementar o modelo de span, a persistência e o mapeamento semântico YAML; verificar com teste de convenções diferentes → mesmo `kind`
- [ ] 1.2 Implementar a redacção (segredos, PII, allowlist) antes de qualquer escrita; verificar com testes de `Bearer sk-...`, email, IBAN e casos adversariais
- [ ] 1.3 Implementar `POST /traces/import` (OTLP JSON e formato simples, `incomplete_trace`); verificar com fixtures
- [ ] 1.4 Implementar o SDK de instrumentação e aplicá-lo aos mini-alvos (RAG, ferramentas, routing); verificar que o mini RAG produz os spans e atributos esperados
- [ ] 1.5 Escrever `docs/learn/forensics/01` a `03`; verificar com traces reais dos mini-alvos

## 2. Detecção

- [ ] 2.1 Implementar o motor de regras versionado e as 10 regras da taxonomia com evidence score; verificar com um trace golden por regra
- [ ] 2.2 Implementar os diagnósticos (observação, hipótese, método, check, replay_id) e a ordenação de falhas aninhadas; verificar com o teste rate_limit→fallback→timeout
- [ ] 2.3 Implementar o resumo opcional por LLM com validação de referências; verificar com teste de span inexistente → `invalid_reference`
- [ ] 2.4 Escrever `docs/learn/forensics/04` a `06`; verificar que os exemplos vêm dos testes

## 3. Incidentes e replay

- [ ] 3.1 Implementar os incidentes, as versões, os filtros, o feedback e `GET /metrics`; verificar com testes de filtro e falso positivo
- [ ] 3.2 Implementar o replay em sandbox (stubs mutáveis, mock por omissão, `not_replayable`); verificar com testes
- [ ] 3.3 Implementar o relatório Markdown e a comparação bom vs mau; verificar com o snapshot de um relatório
- [ ] 3.4 Implementar as vistas do painel (lista, árvore de spans, lado a lado, exportar); verificar no browser
- [ ] 3.5 Escrever `docs/learn/forensics/07-replay-seguro.md`; verificar com o teste de stub

## 4. Avaliação

- [ ] 4.1 Criar a suite de fault injection (≥8 cenários incluindo incompletos, redigidos, adversariais e aninhados) com labels e um subconjunto "não visto"; verificar a geração
- [ ] 4.2 Implementar o runner (precisão/recall por tipo, FP, % reproduzidos, exactidão de localização, tempo de laboratório); verificar o relatório com metadados
- [ ] 4.3 Correr a avaliação e documentar os diagnósticos correctos e incorrectos; verificar que os números vêm da run
- [ ] 4.4 Escrever `docs/learn/forensics/08-metricas-de-diagnostico.md`, actualizar as perguntas de entrevista e o compose opcional com Phoenix; verificar a consistência

## Workflow follow-up

- Ligar ao GroundVault/AgentStation/ModelMesh quando estiverem instrumentados.
- Arquivar após revisão.
