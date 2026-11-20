# 02 — Goldens e labels

## O problema

Um dataset golden é a referência fixa com que medimos regressões. Se o dataset muda sem controlo, uma queda de
qualidade pode ser "resolvida" mudando os casos em vez do sistema. Três perguntas precisam de resposta:

1. De onde vem o label (qual é a verdade)?
2. Como sabemos que um caso não mudou entre duas runs?
3. Como evitamos que a saída do sistema contamine o label?

## O que entra e o que sai

- **Entra:** um ficheiro JSONL. A primeira linha é o manifesto; as seguintes são casos.
- **Sai:** um `Dataset` validado com um `content_hash` (SHA-256 do conteúdo canónico), ou uma lista de `Issue`s
  com código, ficheiro e linha.

Exemplo real, a validar o dataset de extração e a inspecionar a contagem:

```
$ ai-eval datasets validate
OK datasets\extraction\golden.jsonl v1.0.0+074607e5cada (46 casos)
OK datasets\minirag\golden.jsonl v1.0.0+a07201dd012a (44 casos)

$ ai-eval datasets stats
Total de casos: 90

Alvo:
  extraction                         46
  minirag                            44

Categoria:
  extraction/edge_number              7
  extraction/happy                    5
  extraction/injection                4
  extraction/missing_field            2
  extraction/multi_item               7
  extraction/negation                 2
  extraction/noisy                    6
  extraction/refund                   4
  extraction/tier                     9
  minirag/abstain                     6
  minirag/factual                    22
  minirag/multi_hop                   6
  minirag/security_read               6
  minirag/security_write              4

Severidade:
  critical                           28
  normal                             62
```

## Como funciona por dentro

- Validação em `src/regressionguard/datasets/loader.py` (`parse_dataset`). Cada linha é lida separadamente, por isso
  o erro indica o número exato da linha. Os erros são acumulados, não se para no primeiro.
- O modelo `Case` (`src/regressionguard/datasets/models.py`) usa `extra="forbid"`: um campo mal escrito
  (`catgory`) falha em vez de passar em silêncio.
- A regra "`expected` ou `criteria`" está no `model_validator` de `Case`.
- O hash (`canonical_hash`) serializa o conteúdo com chaves ordenadas. Por isso espaços e a ordem das chaves
  não mudam o hash, mas mudar um único label muda-o. Os testes `tests/test_datasets.py` cobrem os dois casos.
- Cada run guarda `dataset_hash` e `dataset_version`; a comparação recusa runs com hashes diferentes
  (`dataset_version_mismatch`, ver `docs/learn/07-comparacao-emparelhada-bootstrap-mcnemar.md`).

## Porquê esta escolha

- **JSONL e não YAML:** uma linha por caso faz `diff` e `git blame` úteis e permite acrescentar casos sem reescrever o ficheiro.
- **Manifesto na primeira linha:** o ficheiro continua a ser um JSONL puro, sem um segundo formato.
- **Hash do conteúdo canónico e não do ficheiro:** reformatar não deve invalidar baselines; mudar um label deve.
- **`source` obrigatório:** um label sem origem não pode ser auditado. É o campo que mais falta em datasets reais.

## Alternativas

- **Labels só em base de dados:** melhor para equipas grandes, mas o histórico de alterações fica fora do git.
  Fica como evolução (o `store` é uma interface).
- **Gerar casos com um LLM:** rápido, mas o label passa a depender do mesmo tipo de modelo que estamos a avaliar.
  Aqui os casos são escritos à mão a partir da fonte.
- **Hash do ficheiro em bruto:** mais simples, mas um espaço no fim da linha mudava a versão.

## Como falha

- Caso sem `category` ou `severity` inválida: `invalid_case` com linha.
  Testes: `test_case_without_category_is_rejected`, `test_invalid_severity_is_rejected`.
- `id` repetido: `duplicate_case_id`. Teste: `test_duplicate_case_id_is_rejected`.
- Manifesto em falta ou JSON partido: `missing_manifest` e `invalid_json`.
- Labels que o próprio mock não consegue cumprir não são um erro do dataset: aparecem como falhas medidas
  na run baseline. Por isso o baseline não é "100% verde" e as falhas são registadas, não escondidas.
- Caso com `evaluators` desconhecidos: `[unknown_evaluator]` em `ai-eval datasets validate`.

## Perguntas de entrevista

**Porque é que o label não pode vir da saída do sistema?**
Porque então o teste mede consistência, não correção. Um sistema que erra sempre da mesma maneira passaria
em todos os gates. O label tem de vir de uma fonte independente (a FAQ, a mensagem original).

**O que é contaminação de um golden set?**
Quando o conjunto de avaliação influencia o desenvolvimento a ponto de deixar de ser independente: copiar saídas
para os labels, afinar prompts até passar exatamente estes casos, ou reutilizar casos de treino. Mitigação:
versões, revisão do label contra a fonte e manter parte dos casos fora de qualquer iteração.

**Porque é que se usa hash e não só a versão declarada?**
A versão é uma promessa humana; o hash é verificável. Duas pessoas podem editar um caso e esquecer de subir a versão.
O hash apanha essa diferença e recusa a comparação.

**Quantos casos são suficientes?**
Depende do efeito que queremos detetar. Com 30 casos e uma diferença pequena o intervalo de confiança é largo; o
projeto marca `insufficient_sample_size` nesses casos em vez de dar uma conclusão falsa. A regra prática: quanto menor
a regressão que queremos apanhar, mais casos e repetições.
