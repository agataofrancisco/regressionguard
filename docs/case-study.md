# Estudo de caso: detetar quatro regressões controladas

## Pergunta

Um harness de avaliação deteta regressões que um sistema com LLM introduz sem avisar? E cada gate faz o que
promete, sem bloquear mudanças que não regridem?

## Método

- **Sistemas-alvo.** Um mini RAG sobre uma FAQ sintética e uma mini app de extração de encomendas. Ambos têm
  modo mock determinista (sem rede, sem chaves).
- **Dataset.** 90 casos rotulados (46 de extração, 44 de RAG), com categorias de segurança. Labels escritos a
  partir da fonte, não da saída do sistema (`CONTRIBUTING-goldens.md`).
- **Baseline.** Configuração `v1`.
- **Regressões.** Quatro configurações, cada uma com um critério de sucesso escrito antes de correr:
  1. `no-citations`: o RAG deixa de citar fontes.
  2. `unauthorized-select`: o RAG faz `SELECT` sobre `customers`, tabela não autorizada.
  3. `schema-change`: a extração renomeia `total` para `total_eur`.
  4. `k1`: o `top_k` do retrieval desce de 5 para 1.
- **Critério.** Cada regressão tem de fazer falhar o gate crítico esperado. `v1` contra `v1` não pode gerar gate crítico.
- **Medição.** Modo mock, 1 repetição, comparação emparelhada com IC 95% por bootstrap e McNemar exato.

## Resultados (medidos)

Tabela de `pytest -m lab -s`:

```
k1                   exit=1 regressoes=3  sucesso 0.778->0.778 gates=critical_pass_rate_drop
no-citations         exit=1 regressoes=21 sucesso 0.778->0.544 gates=citations_regression,critical_pass_rate_drop
schema-change        exit=1 regressoes=38 sucesso 0.778->0.356 gates=schema_regression,critical_pass_rate_drop
unauthorized-select  exit=1 regressoes=5  sucesso 0.778->0.722 gates=security_violations_new,critical_pass_rate_drop
```

| Regressão | Detetada pelo gate esperado | Casos regredidos | Diferença | IC 95% |
|---|---|---|---|---|
| `no-citations` | sim | 21 | −23.3 pp | [−0.322, −0.144] |
| `unauthorized-select` | sim | 5 | −5.6 pp | [−0.111, −0.011] |
| `schema-change` | sim | 38 | −42.2 pp | [−0.522, −0.322] |
| `k1` | sim | 3 | 0.0 pp | [−0.056, +0.056] |

Falsos positivos: `v1` contra `v1` terminou com exit 0 e sem regressões (1 comparação de controlo).

## O que aprendemos

1. **A média pode esconder uma regressão.** Com `k1`, a taxa global não muda (77.8% antes e depois). Três casos
   críticos multi-hop passam a falhar (a categoria `multi_hop` cai 50 pontos), e três casos factuais melhoram
   porque entra menos ruído de contexto. Só o gate sobre casos críticos e o detalhe por categoria o revelam.
2. **Um gate por tipo de risco.** O `unauthorized-select` tem uma diferença pequena (−5.6 pp), mas o gate de
   segurança dispara com 5 casos novos. Um gate de média não o apanharia com a mesma confiança.
3. **Cobertura por categoria conta mais do que o número total de casos.** Sem casos de segurança com tabelas
   proibidas, a regressão `unauthorized-select` passaria.
4. **Um efeito grande não precisa de um p-valor pequeno para bloquear.** O `unauthorized-select` tem p = 0.0625;
   o bloqueio vem do gate de segurança.

## Limitações honestas

- **Tudo é mock.** O mock é determinista: não há variância entre repetições e a latência é sintética. Estes
  resultados validam o pipeline e a lógica estatística; não medem um modelo real. O tamanho de efeito de um
  modelo real é **TODO: medir** em live.
- **O mock tem falhas próprias.** A baseline falha 20 dos 90 casos (negações, quantidades por extenso, injeção
  de instruções, e perguntas sem resposta na FAQ). São limitações do mock, medidas e registadas.
- **Os casos foram escritos por quem escreveu o harness.** Um revisor independente dos labels não foi feito.
- **Não há falsos positivos medidos em live.** A taxa de falsos positivos exige repetições em live.

## Próximos passos

- Correr o modo live com um modelo real, N repetições e `max_usd`, e medir a variância entre execuções.
- Calibrar o juiz LLM com uma amostra rotulada por pessoas (`TODO: medir`).
- Rever os labels com um segundo revisor.
