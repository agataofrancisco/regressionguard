# 06 — Aleatoriedade e repetições

## O problema

Um LLM em modo live não devolve sempre a mesma resposta ao mesmo input. Com temperatura acima de zero a
saída varia; mesmo com temperatura 0, o provedor pode mudar o modelo por baixo (e a seed só é respeitada
quando o provedor a suporta). Uma única execução por caso pode passar numa run e falhar na seguinte sem que
nada tenha mudado. Se o gate lê uma única tentativa, o PR é bloqueado por ruído.

A resposta usual é **repetir** cada caso N vezes e tratar o resultado como uma taxa, não como um booleano.

## O que entra e o que sai

- **Entra:** `--repeats N` e `--seed S`. A repetição `r` usa a seed `S + r`.
- **Sai:** por caso, `pass_rate` (passagens / N), `flaky` (verdadeiro se `0 < pass_rate < 1`), latências de
  cada repetição, custo somado e as taxas de cada avaliador.

Execução real no código deste repositório, com três repetições e seed 7:

```
$ ai-eval run --suite full --config-set v1 --mode mock --repeats 3 --seed 7 --tag repeticoes-demo
Run 20261120T143941Z-47cfc5 | complete | modo mock | suite full
Casos 90 | sucesso 77.8% | criticos 75.0%
Falhas de seguranca 0 | instaveis 0
Latencia p50 7.02 ms p95 9.65 ms (synthetic-mock) | custo 0 USD
provider: mock (deterministico; latencia sintetica; custo zero)
```

O resultado é "instáveis 0" porque o mock é determinista: as três repetições são idênticas. Isto é o comportamento
correto e é também o aviso: **o mock não mede variância**. A variância só aparece em live.

E o orçamento, sem `--max-usd`, recusa antes de qualquer chamada:

```
$ ai-eval run --suite full --config-set v1 --mode live
erro de configuracao: o modo live exige --max-usd
exit=2
```

## Como funciona por dentro

- O ciclo de repetições está em `src/regressionguard/runner/run.py` (`run_suite`). Para cada caso, `range(repeats)`
  chama o alvo com `seed = opts.seed + repeat` e avalia as saídas uma a uma.
- A taxa é calculada em `_aggregate_case` (mesmo ficheiro): `pass_rate = sum(repeat_passed) / repeats`.
- `flaky = 0 < pass_rate < 1` (`run.py`, em `_aggregate_case`).
- Um caso passa numa repetição apenas se nenhum avaliador **primário** falhar e o alvo não devolver erro
  (`evaluate_output`). Os avaliadores secundários (juiz) não entram nesta conta.
- Limiar de decisão: `passed = pass_rate >= 0.5` (`FAILED_THRESHOLD` em `runner/summary.py`). É um limiar de
  maioria. Para comparações de gates, a unidade é a taxa, não o booleano.

Teste que cobre a regra do exemplo do spec (passa em 3 de 5 repetições, `pass_rate = 0.6`, marcado `flaky`):
`tests/test_runner.py::test_repeats_produce_pass_rate_and_flaky_flag`.

## Porquê esta escolha

- **Taxa e não booleano.** Um caso que passa 3 em 5 é informação. Um booleano esconde essa diferença.
- **Seed por repetição (`S + r`).** Cada repetição é diferente mas reprodutível. Uma falha pode ser repetida
  com a mesma seed para investigação.
- **Orçamento antes de começar.** O modo live exige `--max-usd` porque uma suite de 90 casos com 10 repetições
  e um modelo caro pode custar mais do que se pensa. O erro acontece antes da primeira chamada.

## Alternativas

- **Temperatura 0 e uma repetição.** Simples e barato, mas não elimina a variação do provedor e não permite
  medir a instabilidade, que é um dos sinais de qualidade.
- **Intervalos de confiança por caso (bootstrap intra-caso).** Mais preciso, mas com 5 repetições a estimativa
  por caso é fraca. Por isso o bootstrap é feito sobre casos (ver `docs/learn/07`).
- **Votação entre repetições (maioria) como saída.** Muda a saída que se avalia; aqui avalia-se cada repetição
  e agrega-se o resultado.

## Como falha

- Orçamento atingido: a run para e fica `incomplete: budget_reached`. Não é usada para gates. Teste:
  `tests/test_runner.py::test_budget_stops_run_and_marks_incomplete` (dois custos de 0.5 com teto de 1.2 param
  antes do terceiro).
- Live sem teto: recusa com exit 2. Teste: `tests/test_cli.py::test_live_without_max_usd_is_refused_before_any_call`.
- Erro do alvo: vira `error_rate` e a repetição falha, sem derrubar a run. Teste: `test_target_exception_becomes_error_output`.
- Limitação conhecida: a estimativa do orçamento usa o maior custo observado. A primeira chamada não tem
  estimativa, por isso o orçamento pode ser ultrapassado no máximo por uma chamada. Ver "Decisões novas" no
  relatório de execução.

## Perguntas de entrevista

**Quantas repetições são suficientes?**
Depende da variância do caso e do efeito que queremos detetar. Com `pass_rate` estimado sobre N repetições, o erro
padrão de uma proporção p é aproximadamente sqrt(p(1-p)/N). Para N=5 e p=0.5 é cerca de 0.22: um caso com 3 em 5
é indistinguível de 50%. Por isso a estatística final usa os casos (N grande), não as repetições (N pequeno).

**Porque é que mock deterministico não basta para validar um gate?**
Porque o gate precisa de saber se uma mudança real desloca a distribuição das saídas. Um mock determinista tem
variância zero, por isso qualquer diferença observada é uma diferença de regra, não de amostragem. Serve para
testar o pipeline, não para medir um modelo.

**O que é flakiness num sistema LLM e como se distingue de uma regressão?**
Flakiness é variação entre repetições com o mesmo código e a mesma configuração. Uma regressão é uma mudança
da taxa média entre versões. A medição de flakiness (casos com `0 < pass_rate < 1` na mesma versão) é o que
permite não confundir as duas coisas.
