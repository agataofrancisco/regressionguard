# 07 — Comparação emparelhada: bootstrap e McNemar

## O problema

Queremos saber se o candidato é pior do que o baseline. A ingenuidade é comparar as médias globais:
"77.8% contra 76.0%, logo piorou". Mas as duas médias vêm dos mesmos 90 casos, e alguns casos são
sistematicamente fáceis e outros difíceis. A variância entre casos é grande e não tem nada a ver com a mudança.
A pergunta certa é: **para cada caso, o que mudou?**

Dois problemas:
1. **Emparelhamento.** A mesma pergunta foi feita às duas versões. A diferença por caso remove a dificuldade do caso.
2. **Incerteza.** Uma diferença de 2 pontos percentuais em 90 casos pode ser ruído. Precisamos de um intervalo.

## O que entra e o que sai

- **Entra:** duas `RunRecord` (baseline e candidato) do mesmo dataset e do mesmo modo, e um `GatesConfig`.
- **Sai:** `ComparisonReport` com a diferença média emparelhada, o IC 95%, o p-valor de McNemar, as contagens de
  pares discordantes, o estado de amostra (`insufficient_sample_size`), as regressões e os gates.

Saída real de `ai-eval compare` para o baseline contra `no-citations` (run do laboratório):

```
Candidato 20261120T142927Z-6517c8 contra baseline 20261120T142919Z-f52b94 (90 casos)
Sucesso: 77.8% -> 54.4% (diferenca -23.3 pp)
IC 95% da diferenca: [-0.322, -0.144] | McNemar p=1e-06 (so baseline 21, so candidato 0)
Gates:
  [critical] FALHOU        citations_regression (valor 27, limiar 0.0)
  [critical] FALHOU        critical_pass_rate_drop (valor 0.3929, limiar 0.02)
Recomendacao: rollback para 20261120T142919Z-f52b94 (nao executado)
exit=1
```

## Como funciona por dentro

- **Diferença por caso.** `d_i = pass_rate_cand_i − pass_rate_base_i` (`src/regressionguard/comparison/engine.py`,
  dentro de `compare`). Os casos são o conjunto comum às duas runs; os que não existem nas duas são listados.
- **Bootstrap percentílico** (`src/regressionguard/comparison/stats.py`, `paired_bootstrap_ci`). Reamostra os
  **casos** com reposição 10 000 vezes (`rng.integers` com seed 1234), calcula a média de cada reamostragem e
  devolve os percentis 2.5 e 97.5. Não assume normalidade. A seed fixa torna o resultado reproduzível.
- **McNemar exacto** (`mcnemar_exact`). Cada caso é binário: passa se `pass_rate ≥ 0.5`. Contam-se os pares
  discordantes: `b` = passa só no baseline, `c` = passa só no candidato. Sob a hipótese nula, `b` segue
  Binomial(b+c, 1/2). O p-valor bilateral é `binomtest(min(b,c), b+c, 0.5)`.
- **Amostra insuficiente** (`compare`). Marcada se há menos de `min_cases` casos (30 por omissão) ou se o IC
  contém zero e tem largura acima de `max_ci_width` (0.20). Nesses casos o relatório diz "não conclusivo".

## Porquê esta escolha

- **Bootstrap sobre casos.** Reamostrar casos respeita a unidade de independência (o caso). Reamostrar repetições
  do mesmo caso subestimaria a incerteza.
- **McNemar para o caso binário.** É o teste correto para dados emparelhados binários. Um teste t de amostras
  independentes ignoraria o emparelhamento e daria um p-valor errado.
- **Exacto e não aproximado.** Com poucos pares discordantes a aproximação qui-quadrado é fraca; `binomtest` é exacto.
- **Seed fixa e número de reamostragens publicado no relatório.** Um IC sem método declarado não é auditável.

## Alternativas

- **Teste t emparelhado sobre `d_i`.** Válido se `d_i` for aproximadamente normal. Com diferenças discretas
  (0, 0.5, 1) a normalidade falha; o bootstrap evita essa suposição.
- **Bootstrap intra-caso.** Reamostrar repetições dá uma incerteza por caso, não entre casos. Não responde à
  pergunta "esta versão é pior em geral?".
- **Bayesiano (Beta-Binomial por caso).** Mais informativo, mas exige escolher um prior, que é uma decisão
  adicional difícil de defender a uma equipa.

## Como falha

Testes em `tests/test_stats_compare.py`:

- `test_mcnemar_hand_values`: `b=5, c=0` dá `p = 2·(1/2)^5 = 0.0625`; `b=10, c=2` dá `p ≈ 0.0386`.
- `test_bootstrap_detects_known_effect_and_rejects_null`: com efeito real de 0.3 o IC exclui zero; com efeito nulo, inclui.
- `test_bootstrap_is_reproducible_with_fixed_seed`.
- `test_known_improvement_is_significant_and_not_a_regression`: 30 casos vão de 0 para 1, a média emparelhada é 0.5
  e o IC fica acima de zero.
- `test_small_sample_is_flagged_inconclusive`: 10 casos ativam `insufficient_sample_size`.

Limitações:

- **Repetições não entram no bootstrap.** O `pass_rate` por caso já as resume. Com 1 repetição, `pass_rate` é
  binário e o McNemar é exato sobre o caso inteiro. Com N repetições, o McNemar usa o limiar de maioria, e isso é
  uma aproximação que o relatório declara.
- **Multiplicidade.** Com muitos gates e muitas categorias, algum p-valor fica abaixo de 0.05 por acaso. Os gates
  críticos não usam o p-valor para decidir; usam limiares de diferença. O p-valor é informativo.

## Resultados do laboratório (medidos, mock)

Comparação de cada regressão contra o baseline `v1`, 90 casos, 1 repetição, modo mock:

| Regressão | Diferença | IC 95% | McNemar p | Só baseline / só candidato | Gate crítico que falha |
|---|---|---|---|---|---|
| `no-citations` | −23.3 pp | [−0.322, −0.144] | 1e−6 | 21 / 0 | `citations_regression`, `critical_pass_rate_drop` |
| `schema-change` | −42.2 pp | [−0.522, −0.322] | ~0 | 38 / 0 | `schema_regression`, `critical_pass_rate_drop` |
| `unauthorized-select` | −5.6 pp | [−0.111, −0.011] | 0.0625 | 5 / 0 | `security_violations_new`, `critical_pass_rate_drop` |
| `k1` | 0.0 pp | [−0.056, +0.056] | 1.0 | 3 / 3 | `critical_pass_rate_drop` |

O caso `k1` é o mais instrutivo: a média não muda, porque três casos críticos multi-hop regridem e três casos
factuais melhoram (há menos ruído de contexto). Este valor de McNemar não permite concluir nada sobre o efeito
global; o que o detecta é o gate sobre casos críticos e o detalhe por categoria (`multi_hop`: −50 pp).

Notas honestas:
- Estes números são de mock. Não medem a variância de um modelo real. A estrutura estatística está testada; o
  tamanho de efeito real é **TODO: medir** em live.
- O `unauthorized-select` tem IC que exclui zero mas McNemar p = 0.0625. A decisão de bloquear vem do gate de
  segurança (6 casos novos), não do p-valor. É deliberado: um gate de segurança não espera significância.

## Perguntas de entrevista

**Porque é que comparas casos e não médias?**
Porque a média global mistura a dificuldade dos casos com o efeito da mudança. Ao olhar para a diferença por
caso, a dificuldade cancela-se. É a mesma razão pela qual um teste A/B usa o mesmo utilizador nos dois braços
quando pode.

**Explica o McNemar a alguém que não é estatístico.**
Olhamos só para os casos em que as duas versões discordam. Se a mudança não fizesse diferença, cada discordância
seria igualmente provável em qualquer sentido. Se houver muito mais discordâncias num sentido, a mudança tem efeito.

**O que quer dizer um IC de 95%?**
Se repetíssemos o processo de amostragem muitas vezes, cerca de 95% dos intervalos construídos assim conteriam o
valor verdadeiro. Não quer dizer que há 95% de probabilidade de o valor estar naquele intervalo.

**Porque não usar um teste t?**
Porque as diferenças por caso são discretas e não normais, e o teste t não usa o emparelhamento de forma
explícita. O bootstrap não assume a forma da distribuição.

**Quantos casos precisas?**
Para detetar uma queda de 5 pontos com 80% de potência, a ordem de grandeza são várias centenas de pares com
variância moderada. Com 90 casos, o laboratório deteta quedas de 20 pontos ou mais com confiança; quedas de
5 pontos ficam inconclusivas. O relatório marca isto explicitamente.
