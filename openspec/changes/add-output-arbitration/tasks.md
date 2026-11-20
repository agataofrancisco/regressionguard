# Tasks

## 1. Dataset e geração

- [ ] 1.1 Criar o gerador de ≥100 participações sintéticas rotuladas com as dificuldades da spec e o manifesto; verificar com `ai-eval datasets validate` e as estatísticas por dificuldade
- [ ] 1.2 Implementar os candidatos (adaptador compatível com OpenAI e mock com perfis de erro, incluindo correlacionado) com geração paralela, timeout e orçamento; verificar com testes de timeout, `skipped: budget` e erro correlacionado

## 2. Arbitragem

- [ ] 2.1 Implementar a normalização por tipo (datas com ambiguidade, montantes, matrículas, booleanos); verificar com testes de "3/2/2026" ambíguo e montantes por extenso
- [ ] 2.2 Implementar a localização de evidência com offsets no texto original; verificar com testes de valor inventado → `evidence: none` e offsets exactos
- [ ] 2.3 Implementar a fiabilidade histórica (Beta), o score de confiança e a calibração (ECE, reliability diagram); verificar com testes sobre dados com calibração conhecida
- [ ] 2.4 Implementar a decisão por campo, a verificação barata, o juiz consultivo e a flag `suspected_injection`; verificar com testes de `evidence_conflict`, desacordo com orçamento e injecção
- [ ] 2.5 Escrever `docs/learn/arbitration/01` a `05`; verificar que os exemplos vêm dos testes

## 3. API e revisão

- [ ] 3.1 Implementar a persistência e `POST /arbitrations`, `GET /arbitrations/{id}`, `GET .../candidates`, `POST .../human-review` e `GET /metrics` com papéis; verificar com testes de API (422, 403, auditoria)
- [ ] 3.2 Implementar a exportação de revisões para JSONL golden (`source: human_review`); verificar com teste
- [ ] 3.3 Implementar o painel de três colunas com destaque de spans; verificar no browser

## 4. Experiência

- [ ] 4.1 Implementar o runner das 5 estratégias com revisão simulada e as métricas da spec; verificar que corre em mock e gera tabela e gráfico
- [ ] 4.2 Correr a experiência em mock, gravar o relatório com os casos desfavoráveis e os erros correlacionados; verificar que os números vêm da run
- [ ] 4.3 Registar a arbitragem como avaliador opcional nas suites do RegressionGuard; verificar com uma suite que a usa
- [ ] 4.4 Escrever `docs/learn/arbitration/06-custo-vs-qualidade.md`, actualizar as perguntas de entrevista e documentar onde o sistema falha; verificar a consistência com o relatório

## Workflow follow-up

- Execução real manual com 2-3 modelos e `max_spend`.
- Arquivar após revisão.
