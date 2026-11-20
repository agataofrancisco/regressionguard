# Tasks

## 1. Registo

- [ ] 1.1 Criar modelos e migrações (prompts, versions, aliases, datasets, experiments, assignments, exposures, evaluation_runs, audit_events) com imutabilidade e `lock_version`; verificar com testes de 409 por versão imutável e alias concorrente
- [ ] 1.2 Implementar o render Jinja2 sandboxed com variáveis tipadas e a detecção de PII no template; verificar com testes de `missing_variable` e `pii_detected`
- [ ] 1.3 Implementar `POST /prompts`, `POST /prompts/{id}/versions`, `PUT .../aliases/{name}` e `GET .../resolve` com tenants e papéis, auditoria e exportação YAML/JSON; verificar com testes de 404 cross-tenant e exportação
- [ ] 1.4 Escrever `docs/learn/promptops/01` a `03`; verificar os exemplos com testes

## 2. Experiências

- [ ] 2.1 Implementar a experiência offline congelada (mesmo dataset/modelo/settings, `unfair_comparison`) via runner do RegressionGuard; verificar com teste
- [ ] 2.2 Implementar a atribuição por hash com persistência, exposições idempotentes, consentimento e kill switch; verificar com testes de estabilidade, distribuição 10/90 sobre 10 000 sintéticos, duplicado e stop
- [ ] 2.3 Implementar os resultados com IC (Wilson/Newcombe, bootstrap), MDE e `insufficient_sample_size`; verificar com testes sobre dados com efeito conhecido e com amostra pequena
- [ ] 2.4 Escrever `docs/learn/promptops/04` e `05`; verificar com a simulação sintética

## 3. Gates, CI e painel

- [ ] 3.1 Implementar a promoção condicionada a gates e o rollback com auditoria; verificar com testes de promoção bloqueada, aceite e rollback
- [ ] 3.2 Criar o formato `prompts/*.yaml` e `.github/workflows/promptops.yml` (diff → versões candidatas → compare mock → check); verificar com um PR de exemplo mau bloqueado e um bom aprovado, documentados com output real
- [ ] 3.3 Implementar o painel (editor com variáveis, diff de versões, matriz de resultados, custos/latências, vencedores ou aviso, rollback, timeline de versões); verificar no browser
- [ ] 3.4 Escrever `docs/learn/promptops/06` e `07`, actualizar as perguntas de entrevista e documentar a integração opcional com Langfuse; verificar a consistência

## Workflow follow-up

- Gravar a demo da timeline de versões e da comparação.
- Arquivar após revisão.
