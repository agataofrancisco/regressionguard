# 04 — Avaliadores semânticos

## O problema

Muitas respostas não são binárias: "Lisboa" e " lisboa " são a mesma resposta; uma resposta com todos os factos
certos e uma frase a mais não deve falhar como uma resposta errada. Os avaliadores semânticos comparam com
**tolerância explícita**. A tolerância tem de ser declarada, senão o resultado não é reproduzível.

## O que entra e o que sai

- **Entra:** o label (`expected`) e o texto ou os campos da saída, mais critérios opcionais (`normalize`, `threshold`).
- **Sai:** `score` entre 0 e 1 e `details` com a normalização usada, a precisão, a cobertura e o limiar.

Valores reais, executados no código:

```
exact_match("Lisboa", " lisboa ") -> passed=True score=1.0
    details={'normalization': ['strip', 'casefold'], 'expected': 'lisboa', 'actual': 'lisboa'}

token_f1_scores("a b c d", "a b x") -> (precisão 0.6667, cobertura 0.5000, F1 0.5714)
```

O F1 à mão: tokens comuns = 2; precisão = 2/3; cobertura = 2/4; F1 = 2·(2/3)·(1/2) / ((2/3)+(1/2)) = 4/7 ≈ 0.5714.
Verificado por `test_token_f1_matches_hand_computed_value`.

## Como funciona por dentro

- `exact_match` (`src/regressionguard/evaluators/semantic.py:40`): normaliza os dois lados com os passos declarados
  (`strip` e `casefold` por omissão) e compara a igualdade.
- `token_f1` (`semantic.py:76`): normaliza com `strip_citations`, `strip_punct`, `casefold`, `strip_accents` e
  `collapse_ws`. Remover citações é necessário: `[faq-001]` não é conteúdo. A função pura `token_f1_scores`
  (`semantic.py:57`) usa `Counter` (multiconjuntos), por isso repetir um token conta.
- `field_f1` (`semantic.py:129`): para objetos. Um campo conta como correto se `values_equal` o aceitar.
  Precisão = coincidências / campos na saída; cobertura = coincidências / campos no esperado.
- `values_equal` (`semantic.py:101`): regras por tipo. `bool` antes de `int` (em Python `True == 1`);
  números com tolerância absoluta `NUMERIC_TOLERANCE = 0.005`; texto normalizado; listas sem ordem (multiconjunto);
  dicionários com as mesmas chaves e valores iguais.
- `similarity` (`semantic.py:164`): `difflib.SequenceMatcher.ratio()` com limiar configurável. Para "abc" vs "abd":
  2·M/T = 4/6 ≈ 0.6667.

## Porquê esta escolha

- **Tolerância declarada no `details`.** O relatório mostra `normalization: [strip, casefold]`. Quem lê uma falha
  sabe o critério sem ler o código.
- **F1 e não exact match para extração.** Uma extração com 4 campos certos e 1 errado é melhor do que uma com 0 certos;
  o F1 por campo separa estes casos. O exact match trataria as duas como falha.
- **Multiconjuntos.** Um `set` ignora repetições; numa lista de encomendas com a mesma linha duas vezes isso
  esconderia um erro.
- **`bool` antes de `int`.** Sem isto, `refund_requested: 0` passaria a igualar `False`.

## Alternativas

- **Similaridade semântica com embeddings.** Capta paráfrases, mas introduz um modelo de embeddings (custo, e
  resultados que mudam entre versões) e um limiar difícil de justificar. Fica como evolução com limiar calibrado.
- **BLEU/ROUGE.** Métricas de tradução e de resumo; penalizam paráfrases corretas e funcionam mal em respostas curtas.
- **Distância de Levenshtein.** Simples, mas penaliza a ordem das palavras e dá valores altos em textos longos
  muito diferentes.

## Como falha

- `test_exact_match_declares_normalization`, `test_exact_match_fails_on_different_text`.
- `test_token_f1_threshold_and_normalization_details`: F1 de 1.0 com a citação removida; abaixo do limiar falha.
- `test_field_f1_hand_computed_threshold`: 4 de 5 campos corretos dá F1 = 0.8; falha com o limiar 0.9 e passa com 0.79.
- `test_values_equal_rules`: tolerância de 0.005 (12.5 contra 12.504 passa; 12.5 contra 12.52 falha) e `None` contra `0` falha.
- Limitação: `difflib` é sensível à ordem e ao comprimento; é um sinal grosseiro. Para respostas longas usa-se `token_f1`.

## Perguntas de entrevista

**Porque é que o F1 penaliza tanto a verbosidade?**
A precisão cai quando a resposta tem tokens que não estão na referência. Um RAG que cola três frases quando a
resposta é uma tem cobertura alta e precisão baixa; o F1 apanha isso e a cobertura sozinha não.

**Qual é a diferença entre precisão e cobertura num caso de FAQ?**
Precisão: quanto da resposta está correta. Cobertura: quanto da resposta esperada apareceu. Um sistema que responde
"não sei" a tudo tem precisão e cobertura baixas quando o label tem factos.

**Porque é que a tolerância numérica é absoluta e não relativa?**
Para preços em euros, 0.005 é meio cêntimo. Uma tolerância relativa dava margem indevida em valores grandes
(1250.00 contra 1250.90 passaria). A tolerância tem de corresponder à unidade do campo.
