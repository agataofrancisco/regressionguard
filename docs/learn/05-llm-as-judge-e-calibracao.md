# 05 — LLM-as-judge e calibração

## O problema

Algumas qualidades (tom, fidelidade a uma fonte, utilidade) não se verificam com regras. Um LLM pode julgar essas
qualidades, mas um juiz LLM tem vieses (prefere respostas longas, favorece o próprio modelo) e pode concordar
consigo próprio sem concordar com pessoas. Por isso o juiz é um **sinal secundário**.

## O que entra e o que sai

- **Entra:** uma rubrica versionada (ficheiro Markdown), o input, o label e a saída, e um `Judge` (LLM ou fake).
- **Sai:** um `EvalResult` com `details.signal = "secondary"`, o hash da rubrica (`rubric_sha256`), o limiar e a
  justificação. Para calibração, um `Calibration` com `n`, `agreement` e `kappa`.

Exemplo real de calibração (juiz `[T,T,F,F]`, humanos `[T,F,F,F]`):

```
cohens_kappa([True, True, False, False], [True, False, False, False])
-> Calibration(n=4, agreement=0.75, kappa=0.5)
```

Concordância observada 3/4 = 0.75. Concordância esperada ao acaso: pe = 0.5·0.25 + 0.5·0.75 = 0.5.
Kappa = (0.75 − 0.5) / (1 − 0.5) = 0.5, moderado. Verificado por `test_cohens_kappa_hand_computed_value`.

## Como funciona por dentro

- `llm_judge` (`src/regressionguard/evaluators/judge.py:35`): sem juiz configurado devolve `judge_disabled` e não chama
  nada. Com juiz, lê a rubrica pelo caminho do caso, calcula o SHA-256 e chama `score(...)`.
- O registo marca o avaliador com `secondary=True` (`judge.py:32`). O efeito dessa marca está no runner: um caso
  passa se todos os avaliadores **primários** passarem; os secundários são registados mas não entram nessa decisão.
  Por isso um juiz com nota alta não resgata um caso que falhou o schema.
- `cohens_kappa` (`judge.py:74`): kappa de Cohen para duas classificações binárias, κ = (p_o − p_e) / (1 − p_e), com
  `p_e` calculado a partir das marginais. Os casos degenerados (`p_e = 1`) são tratados explicitamente.
- `calibrate` (`judge.py:90`): binariza as notas do juiz com um limiar e compara com os labels humanos.

## Porquê esta escolha

- **Rubrica versionada com hash.** Se a rubrica muda, o hash muda e a comparação com runs antigas fica explícita.
- **Kappa e não percentagem de acordo.** Com 90% de casos negativos, um juiz que responde sempre "não" tem 90% de
  acordo e kappa zero. O kappa desconta o acordo esperado ao acaso.
- **Secundário.** Um gate crítico não pode depender de um modelo cuja fiabilidade ainda não foi medida.

## Alternativas

- **Juiz como sinal primário.** Mais cobertura, mas a decisão herda os vieses do juiz sem medição.
- **Juiz pareado (A contra B).** Mais estável do que a nota absoluta para comparar duas versões, mas mais caro e não
  serve para um caso isolado. Fica como evolução.
- **Temperatura 0 numa só chamada.** Reduz variância, mas não elimina viés; por isso a calibração é obrigatória.

## Como falha

- `test_llm_judge_is_skipped_without_judge`: sem juiz o avaliador não decide nada.
- `test_llm_judge_low_score_fails`: nota 0.1 com limiar 0.5 falha com `judge_low_score`.
- `test_cohens_kappa_edge_cases`: amostras vazias ou com tamanhos diferentes lançam `ValueError`.
- Limitação: calibrar com amostra pequena dá kappa instável. Recomenda-se pelo menos 30 itens humanos (o mesmo
  mínimo de `min_cases`).
- **TODO: medir** a concordância do juiz com labels humanos. Não existe amostra rotulada por pessoas neste
  repositório, por isso nenhum número de concordância é reportado.

## Perguntas de entrevista

**Porque é que o kappa é melhor do que a percentagem de acordo?**
Porque corrige o acordo que se obteria ao acaso. Em classes desequilibradas a percentagem engana.

**Como detetas que o juiz favorece respostas longas?**
Com um teste de viés: pares com o mesmo conteúdo e comprimentos diferentes, verificando se a nota sobe com o
comprimento. Sem este teste, a nota do juiz é uma suposição.

**Porque não usar o mesmo modelo como alvo e como juiz?**
Porque o juiz tende a preferir o próprio estilo de resposta. Se for inevitável, deve ser declarado no relatório e a
calibração deve ser feita com labels humanos.
