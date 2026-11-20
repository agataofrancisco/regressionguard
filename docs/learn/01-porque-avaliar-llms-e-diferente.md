# 01 — Porque avaliar LLMs é diferente

## O problema

Em software clássico, um teste que passa hoje passa amanhã (determinismo). Com LLMs há três fontes de
variação que tornam isto falso:

1. **Amostragem.** Com `temperature > 0`, a mesma entrada produz saídas diferentes.
2. **Dependências externas.** Uma troca silenciosa de versão do modelo muda o comportamento sem
   alterar uma linha de código.
3. **Sensibilidade a pequenas mudanças.** Uma vírgula no prompt ou um `top_k` de 5 para 1 pode
   degradar um subconjunto de casos.

Consequência: uma única execução não diz nada. Precisamos de repetições, de um conjunto de casos
fixo e de comparação estatística.

## O que o RegressionGuard faz diferente

| Aspeto | Teste unitário | RegressionGuard |
|---|---|---|
| Unidade | Uma asserção | Um dataset de casos |
| Resultado | Passa/falha | Taxa de sucesso com intervalo de confiança |
| Referência | Valor esperado fixo | Baseline da versão anterior, emparelhado caso a caso |
| Custo | Zero | Por caso e por run (medido) |
| Decisão | Verde/vermelho | Gate crítico (bloqueia) ou aviso (informa) |

## Fluxo mental

1. Um **alvo** é o sistema (prompt + modelo + parâmetros + retrieval).
2. Um **baseline** é uma run de uma configuração conhecida.
3. Um **candidato** é uma run da configuração proposta.
4. A **comparação** é feita pares a pares sobre os mesmos casos. Não se comparam médias globais
   de conjuntos diferentes.

## Como falha (e como o projeto se protege)

- *Falso positivo:* um caso instável parece regressão. Protecção: repetições e a marca `flaky`.
- *Falso negativo:* uma regressão real não é detectada porque o conjunto de casos é pequeno.
  Protecção: `insufficient_sample_size` e o mínimo de casos configurável.
- *Mock enganador:* um modo mock determinístico não tem variância real. Protecção: os relatórios mock
  são etiquetados `provider: mock` e as estatísticas de variância só têm significado em modo live.

## Perguntas de entrevista

**Porque é que a média global pode esconder uma regressão?**
Uma queda de 5 pontos pode concentrar-se numa categoria crítica (por exemplo, segurança) enquanto a
média geral sobe por causa de casos fáceis. Por isso os gates olham para categorias e severidade.

**Porque não usar temperatura 0 e evitar o problema?**
Temperatura 0 não garante determinismo em todos os provedores, e mesmo assim não elimina a
sensibilidade a mudanças de prompt. E o produto em produção não corre com temperatura 0.

**Qual é a diferença entre avaliar e observar?**
Observar (tracing, Langfuse, Phoenix) mostra o que aconteceu em produção. Avaliar decide, antes de
um deploy, se uma mudança é aceitável contra um conjunto fixo de casos. As duas coisas são
complementares.
