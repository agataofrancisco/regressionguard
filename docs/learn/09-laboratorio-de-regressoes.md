# 09 — Laboratório de regressões

## O problema

Um harness de avaliação só merece confiança se detetar regressões conhecidas e não inventar outras. Por isso
o repositório inclui quatro regressões controladas, criadas deliberadamente, com um critério de sucesso escrito
antes de correr:

1. **`no-citations`** — o mini RAG deixa de citar as fontes.
2. **`unauthorized-select`** — o mini RAG faz um `SELECT` sobre a tabela `customers`, que não está autorizada.
3. **`schema-change`** — a extração renomeia `total` para `total_eur` na saída.
4. **`k1`** — o `top_k` do retrieval desce de 5 para 1.

Critério: cada regressão tem de fazer falhar o gate crítico correspondente, e a comparação de `v1` contra `v1`
não pode gerar nenhum gate crítico (falso positivo).

## O que entra e o que sai

- **Entra:** o conjunto `v1` (baseline) e cada conjunto de regressão em `targets/sets/`, os 90 casos golden e
  `config/gates.yaml`.
- **Sai:** para cada regressão, um `ComparisonReport` com exit code, gates e lista de regressões.

Saída real de `pytest -m lab -s`, que imprime a tabela do estudo de caso:

```
k1                   exit=1 regressoes=3  sucesso 0.778->0.778 gates=critical_pass_rate_drop
no-citations         exit=1 regressoes=21 sucesso 0.778->0.544 gates=citations_regression,critical_pass_rate_drop
schema-change        exit=1 regressoes=38 sucesso 0.778->0.356 gates=schema_regression,critical_pass_rate_drop
unauthorized-select  exit=1 regressoes=5  sucesso 0.778->0.722 gates=security_violations_new,critical_pass_rate_drop
```

## Resultados (medidos, modo mock, 1 repetição, 90 casos)

| Regressão | Detetada | Gate crítico esperado | Regressões | Falsos positivos (v1 vs v1) |
|---|---|---|---|---|
| `no-citations` | sim | `citations_regression` | 21 | 0 |
| `unauthorized-select` | sim | `security_violations_new` | 5 | 0 |
| `schema-change` | sim | `schema_regression` | 38 | 0 |
| `k1` | sim | `critical_pass_rate_drop` | 3 | 0 |

Falsos positivos: a comparação `v1` contra `v1` terminou com exit 0 e sem regressões. Em 90 casos com saídas
determinísticas isto é o esperado. **Não é uma medição de falsos positivos em live**: com um modelo real, a mesma
comparação deve ser repetida com N repetições e a taxa de falsos positivos medida sobre várias execuções
independentes. **TODO: medir** em live.

## Como funciona por dentro

- As regressões são **configurações**, não código. Cada uma é um YAML em `targets/minirag/configs/` ou
  `targets/extraction/configs/` com um comentário a dizer o que muda:
  - `citations: false` (`no-citations.yaml`);
  - `extra_queries: [customers]` (`unauthorized-select.yaml`), que faz a mesma consulta `SELECT` sobre a tabela
    proibida quando a pergunta menciona uma encomenda;
  - `field_map: {total: total_eur}` (`schema-change.yaml`);
  - `top_k: 1` (`k1.yaml`).
- Os conjuntos (`targets/sets/*.yaml`) agrupam a configuração de cada alvo. A regressão aplica-se só ao alvo que
  altera; o outro fica em `v1`.
- O teste `tests/test_lab.py` (marcado `lab`) corre as cinco configurações e verifica o gate esperado para cada
  regressão, o falso positivo e a tabela impressa.

## Porquê esta escolha

- **Regressões como configuração.** Mudar uma linha num YAML é o tipo de mudança que acontece em produção. Escrever
  uma regressão em código seria testar outra coisa.
- **Critério escrito antes.** Sem isto, qualquer resultado parece uma confirmação.
- **Uma regressão por gate.** Cada regressão tem um gate esperado. Se uma regressão disparar um gate não esperado, é
  informação útil (o gate pode estar mal definido).

## Alternativas

- **Injetar falhas aleatórias no código do alvo.** Mais realista em alguns casos, mas não reprodutível e mais
  difícil de explicar.
- **Usar apenas uma regressão.** Não testaria que cada gate é independente.

## Como falha (e o que isso ensina)

- **O `k1` não aparece na média.** A taxa global fica em 77.8% antes e depois. Três casos críticos
  multi-hop caem para zero, e três casos factuais sobem, porque com `top_k=1` entra menos ruído no contexto. O gate
  de casos críticos é o único que o deteta. **Lição:** um harness que só olha para a média não apanha esta regressão.
- **`unauthorized-select` só aparece nos casos de segurança.** O `security_violations_new` dispara com 5 casos
  novos. Se a suite não tivesse casos de segurança com `forbidden_access`, esta regressão passaria. **Lição:**
  cobertura por categoria importa tanto como o número de casos.
- **O mock tem limitações que aparecem como falhas no baseline.** Os 90 casos têm 20 falhas na baseline
  (77.8% de sucesso). Exemplos: negações (`Não quero devolver`), quantidades por extenso (`Duas canecas`) e injeção de
  instruções que o extrator por regras não distingue. Estas falhas não são bugs do harness; são o limite do mock,
  e aparecem no relatório como casos falhados no baseline.
- **Uma regressão "de sorte".** Em `schema-change`, `customer_tier` e `refund_requested` não mudam, mas a F1 por
  campo cai abaixo do limiar em todos os casos com `total`. Por isso o gate de schema dispara com 46 casos novos,
  não só com os casos em que o valor mudou.

## Perguntas de entrevista

**Como validaste que o harness detecta regressões?**
Criei quatro regressões controladas, com um critério de sucesso escrito antes de correr, e verifiquei que cada uma
faz falhar o gate esperado. Também verifiquei o falso positivo com a comparação do baseline contra si próprio.

**Porque é que o falso positivo com mock não chega?**
Porque o mock é determinista: não há variância para que um falso positivo apareça. O teste mostra que a lógica
não inventa regressões; não mostra a taxa de falsos positivos de um modelo real, que exige repetições em live.

**Qual é o risco de um laboratório deste tipo?**
Que as regressões sejam demasiado óbvias e o harness pareça melhor do que é. A regressão `k1` é a mais honesta
porque não aparece na média, e a `unauthorized-select` tem um efeito pequeno em percentagem. Por isso o laboratório
tem regressões de tamanhos diferentes.

**Porque não basta um teste unitário para cada gate?**
Um teste unitário verifica o gate isolado. O laboratório verifica o pipeline completo: alvo, avaliadores, run,
comparação, gate e código de saída. Um bug na ligação entre as partes passa nos testes unitários e não passa aqui.
