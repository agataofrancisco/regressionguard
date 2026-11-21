# 10 — Perguntas de entrevista

Cada resposta aponta para o código ou o teste que a sustenta. Onde a resposta depende de medição em live, isso
está dito.

## Avaliação de LLMs

**1. Porque é que testes unitários não chegam para LLMs?**
A saída varia e a qualidade é uma propriedade de um conjunto de casos, não de um caso. Afirmamos uma taxa com
intervalo de confiança, não `f(x) == y`. Ver `learn/01`.

**2. O que é um golden set e o que o torna útil?**
Um conjunto fixo de casos com labels de uma fonte independente, versionado por hash. Útil se for rastreável; sem
`source` e sem hash não se audita. Ver `learn/02` e `dataset_hash` em `runner/records.py`.

**3. Como evitas contaminar o golden set?**
Labels da fonte e nunca da saída do sistema; versões com hash; comparação recusada entre versões diferentes
(`dataset_version_mismatch`). Ver `CONTRIBUTING-goldens.md`.

**4. O que é um caso crítico e como o usas?**
Um caso em que a falha tem custo real. Gates de queda de taxa olham só para casos `critical`. Um gate crítico sem
casos críticos falha fechado (`test_missing_critical_fails_closed`).

## Avaliadores

**5. Porque é que `sql_read_only` usa AST e não regex?**
Regex falha com comentários, maiúsculas e subconsultas, e dá falsos positivos em nomes como `updated_at`. A AST
mostra a estrutura. Ver `learn/03` e `evaluators/deterministic.py`.

**6. Porque é que a lista de permissões é mais segura do que a lista de proibições?**
Uma lista de proibições só apanha o que se lembrou de proibir. Aqui só `SELECT`, `UNION`, `INTERSECT` e `EXCEPT`
passam.

**7. O que mede a citação `citations_exist`?**
Que cada citação está nos chunks que o modelo recebeu (`retrieved_ids`). Um id que existe na base mas não foi
recuperado é uma alucinação de fonte.

**8. Explica o F1 por token a alguém que não é estatístico.**
Precisão: quanto da resposta está na referência. Cobertura: quanto da referência aparece na resposta. F1 é a média
harmónica das duas. Ver o cálculo verificado em `test_token_f1_matches_hand_computed_value` (4/7).

**9. Porque é que a tolerância numérica é absoluta?**
Para valores em euros, 0.005 é meio cêntimo. Uma tolerância relativa daria margem indevida em valores grandes.

**10. O que é o kappa de Cohen e porque não usar a percentagem de acordo?**
Kappa corrige o acordo esperado ao acaso. Com classes desequilibradas, um juiz que diz sempre "não" tem acordo
alto e kappa zero.

**11. O juiz LLM pode bloquear um PR?**
Não. É `secondary=True`, e o runner só usa avaliadores primários para decidir a passagem
(`test_judge_cannot_rescue_a_deterministic_failure`). Um juiz com nota alta também não salva um caso que falhou o schema.

## Runs e aleatoriedade

**12. Quantas repetições precisas?**
Depende da variância e do efeito. Com N=5 e p=0.5, o erro padrão é cerca de 0.22: 3 em 5 é indistinguível de 50%.
Por isso a estatística final usa casos, não repetições. Ver `learn/06`.

**13. O que é flakiness e como a mediste?**
Variação entre repetições da mesma versão. Um caso é `flaky` se `0 < pass_rate < 1`
(`test_repeats_produce_pass_rate_and_flaky_flag`). Em mock é sempre zero, e isso é esperado.

**14. Como controlas o custo de uma run live?**
`--max-usd` é obrigatório; sem ele a CLI recusa antes da primeira chamada. Antes de cada chamada estima-se o custo
pelo maior observado; ao atingir o teto a run fica `incomplete: budget_reached` e não serve para gates
(`test_budget_stops_run_and_marks_incomplete`). Limitação: a primeira chamada não tem estimativa.

**15. Porque é que a seed é `S + r` e não a mesma em todas as repetições?**
Com a mesma seed as repetições seriam iguais e não medem nada. `S + r` dá repetições diferentes e reproduzíveis:
uma falha pode ser repetida com a mesma seed.

## Estatística

**16. O que é a comparação emparelhada e porque a usas?**
Calculas a diferença por caso e nunca comparas médias globais de conjuntos diferentes. A dificuldade de cada caso
cancela-se. Ver `comparison/engine.py`.

**17. Como calculas o intervalo de confiança?**
Bootstrap percentílico sobre casos, com 10 000 reamostragens e seed fixa (`comparison/stats.py`). Não assume
normalidade. Os casos são a unidade de independência, não as repetições.

**18. Explica o McNemar.**
Olhas só para os casos em que as versões discordam. Se não houver efeito, cada discordância é igualmente provável em
qualquer sentido. O teste exato é `binomtest(min(b,c), b+c, 0.5)`. Verificado com `b=5, c=0` dar 0.0625.

**19. O que quer dizer um IC de 95%?**
Num processo de amostragem repetido, cerca de 95% dos intervalos construídos assim conteriam o valor verdadeiro.
Não é uma probabilidade de 95% para o valor fixo.

**20. Quando é que uma comparação é "não conclusiva"?**
Quando há menos de `min_cases` casos (30) ou quando o IC contém zero e é mais largo do que `max_ci_width`. O relatório
marca `insufficient_sample_size`. A suite smoke (28 casos) cai nesta marca, e isso aparece no output.

**21. Quantos casos precisas para detetar uma queda de 5 pontos?**
Várias centenas de pares com variância moderada, para potência de 80%. Com 90 casos o laboratório deteta quedas
grandes; quedas de 5 pontos ficam inconclusivas, e o relatório diz isso.

## Gates e CI

**22. Porque separas gates críticos de avisos?**
Um aumento de latência pode ser aceitável; uma regressão de segurança não. Misturar as duas bloqueia PRs legítimos
por ruído. Críticos saem com 1; avisos com 0.

**23. O que faz um gate falhar fechado?**
Um gate crítico com `passed is None` (sem dados) conta como falhado. Um "não avaliável" não é uma aprovação.

**24. Porque é que o rollback é só recomendado?**
Um rollback automático é uma ação irreversível sobre produção decidida por um harness. O sistema grava
`recommendation.applied = False` e mostra "nenhum rollback foi executado".

**25. Porque é que PRs de forks não recebem segredos e o live é manual?**
Um PR de fora pode alterar o workflow para imprimir o segredo. O live só corre em `workflow_dispatch`, com
`max_usd` validado e, se o dono quiser, aprovação via `environment`. Ver `eval.yml`.

**26. Como é que o baseline fica atualizado na CI?**
O job de `push` para `main` recria o artefacto `baseline` com a mesma suite. Os PRs descarregam o último e
comparam. Se o dataset mudou, a comparação é recusada com `dataset_version_mismatch`.

## Arquitetura e engenharia

**27. Porque é que o pacote de comparação se chama `comparison` e não `compare`?**
Para não sombrear a função pública `regressionguard.compare`. Ver `decisions.md`, N1.

**28. Porque é que a run é reconstruída a partir de tabelas e não de um blob JSON?**
Para que as consultas SQL e a comparação leiam a mesma fonte. A reconstrução é testada com igualdade completa,
incluindo a ordem de avaliadores e casos (coluna `seq`, `test_store_round_trip_rebuilds_identical_run`).

**29. Como validaste que o harness detecta regressões?**
Quatro regressões controladas com critério escrito antes de correr; cada uma faz falhar o gate esperado
(`pytest -m lab`). Também verificaste o falso positivo com `v1` contra `v1`. Limitação: é mock.

**30. Porque é que uma média pode esconder uma regressão?**
Porque casos fáceis podem subir enquanto casos críticos caem. No laboratório, `k1` mantém a média em 77.8% e
faz cair três casos críticos multi-hop. Por isso os gates olham para severidade e categoria.

**31. Como garantes que um dado mal formado não parte o parser?**
Funções de parsing puras e defensivas (`as_text`, `rule_extract`, `dig`). Dados de alvo passam por Pydantic com
`extra="forbid"`. Erros de conteúdo viram `error` no resultado, não exceções (`test_http_target_reports_errors_instead_of_raising`).

**32. O que acontece quando um avaliador tem um bug?**
A exceção é apanhada e vira `evaluator_error:<tipo>` no resultado; a run continua
(`test_evaluator_exception_is_contained`).

**33. Porque é que a base de dados recusa um esquema antigo?**
`CREATE TABLE IF NOT EXISTS` não altera tabelas existentes. Sem a verificação, o erro aparecia tarde e
ilegível (`StoreSchemaError`, `test_stale_schema_is_detected_with_clear_error`).

**34. Qual é a diferença entre observar e avaliar?**
Observar (Langfuse, Phoenix) mostra o que aconteceu em produção. Avaliar decide, antes do deploy, se uma mudança
passa num conjunto fixo. São complementares; as integrações estão apenas documentadas em `integrations.md`.

**35. Quais são as limitações conhecidas deste harness?**
Mock não mede variância; o orçamento estima pelo maior custo observado; não há juiz ligado à CLI; o painel
bloqueia o DuckDB durante escritas concorrentes; não há migrações de esquema; o workflow não foi executado no
GitHub. Todas estão em `architecture.md` ou `decisions.md`.
