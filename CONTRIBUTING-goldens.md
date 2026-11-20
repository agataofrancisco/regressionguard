# Como adicionar um caso golden

Um caso golden é uma entrada fixa com um label rastreável. Os casos são a referência com que se medem regressões,
por isso mudá-los sem cuidado invalida todas as comparações anteriores.

## 1. Formato

Cada linha de `datasets/<alvo>/golden.jsonl` é um objeto JSON. Campos obrigatórios:

| Campo | Regra |
|---|---|
| `id` | Estável e único no ficheiro (ex.: `ext-047`, `rag-045`). Nunca reutilizar um id retirado. |
| `input` | O que o alvo recebe. |
| `expected` ou `criteria` | Pelo menos um. `expected` é o label; `criteria` são parâmetros dos avaliadores (ex.: `requires_citation`, `forbidden_tables`). |
| `category` | Texto curto (`happy`, `refund`, `factual`, `security_write`...). Aparece nos relatórios. |
| `severity` | `critical` ou `normal`. Os casos `critical` entram nos gates de queda e na suite `smoke`. |
| `source` | De onde veio o label (ex.: `faq-001`, `sintetico-manual`). Sem `source`, não há auditoria. |
| `evaluators` | Lista de nomes registados (`ai-eval datasets validate` confirma). |

A primeira linha do ficheiro é sempre o manifesto (`{"manifest": {...}}`) com `name`, `version`, `target`, `description`,
`author` e `date`. Não tem de ser a versão que mudou: ver a secção 4.

## 2. Como escolher o label

- O label vem da **fonte**, nunca da saída do sistema. Para o mini RAG, a resposta de referência é uma frase da FAQ
  (`targets/minirag/faq.json`). Para a extração, é o que a mensagem diz.
- Se a fonte não responde à pergunta, o label é **abstenção** (`Não tenho informação suficiente para responder.`).
- Um caso sem resposta certa clara não entra: é ambíguo e enfraquece a medição.
- Usa `severity: critical` só quando uma falha tem custo real (segurança, dados errados, informação inventada).

## 3. Como evitar contaminação

- Não copies a saída atual do alvo para o `expected`. Isso mede se o sistema se mantém igual, não se está certo.
- Não uses o mesmo texto de entrada em dois casos com labels diferentes.
- Não ajustes um label para fazer passar uma regressão que já está detectada: se o label estava errado, cria uma nova versão do dataset e regista o motivo no `description`.
- Não coloques segredos, dados pessoais reais ou nomes de pessoas. Os dados são sintéticos.

## 4. Versões

Alterar qualquer caso muda o hash do conteúdo. Uma comparação só é válida entre runs com o mesmo hash
(`dataset_version_mismatch` recusa o resto). Quando mudares casos:

1. sobe `manifest.version` (semântico: `1.0.0` -> `1.1.0` para acrescentar casos, `2.0.0` para alterar labels);
2. corre `ai-eval run` de novo para o baseline com a nova versão antes de comparar candidatos.

## 5. Passos

1. Escreve o caso com um `id` novo no fim do ficheiro.
2. Valida: `ai-eval datasets validate` (deve imprimir `OK ... (N casos)`).
3. Confirma a contagem: `ai-eval datasets stats`.
4. Corre a suite: `ai-eval run --suite full --mode mock --config-set v1`. O caso aparece na run.
5. Abre um PR com o caso e a justificação do label (`source`). Um segundo revisor confirma o label contra a fonte.

## Exemplo verificado

Adicionar ao fim de `datasets/minirag/golden.jsonl`:

```json
{"id": "rag-999", "input": "Quanto custa o plano Fibra 300?", "expected": "O plano Fibra 300 tem 300 Mbps simétricos e custa 25 euros por mês.", "criteria": {"requires_citation": true}, "category": "factual", "severity": "normal", "source": "faq-001", "evaluators": ["token_f1", "citations_exist"]}
```

`ai-eval datasets validate` passou com `45 casos`. Sem o campo `category`, o validador responde:

```
[invalid_case] datasets\minirag\golden.jsonl:47: category: Field required
```

Com um `id` repetido, responde `[duplicate_case_id] ...:48: id 'rag-001' ja definido na linha 2`.
