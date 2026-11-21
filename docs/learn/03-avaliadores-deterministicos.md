# 03 — Avaliadores deterministas

## O problema

Algumas propriedades de uma saída de LLM são binárias e verificáveis sem julgamento: o JSON é válido, a
ferramenta certa foi chamada, a tabela proibida não foi tocada, a citação existe no contexto, a SQL só lê.
Um avaliador determinista responde com passa/falha e um motivo estável. É barato, reprodutível e é a base
dos gates críticos.

## O que entra e o que sai

- **Entra:** um `EvalContext` (caso, `TargetOutput`, raiz do repositório).
- **Sai:** um `EvalResult` com `passed`, `reason` (código estável) e `details` (o que foi verificado).

Saídas reais dos avaliadores, executadas no código deste repositório:

```
sql UPDATE  -> passed=False reason='sql:write_statement'  details={'sql': "UPDATE orders SET status = 'x'"}
sql SELECT  -> passed=True  reason=None                   details={'checked': 1}
```

E o schema a apontar o campo que falta depois de uma regressão de nome (`total` renomeado para `total_eur`):

```
reason  = 'schema_invalid:required:total'
details = {'errors': ["'total' is a required property"], ...}
```

## Como funciona por dentro

- Registo: `src/regressionguard/evaluators/registry.py:52` (`register`). Nomes duplicados lançam `ValueError`,
  para que dois avaliadores com o mesmo nome não se substituam em silêncio.
- `json_schema` (`src/regressionguard/evaluators/deterministic.py:45`): valida com `Draft202012Validator`.
  Se o erro é `required`, extrai o nome do campo da mensagem, para que o motivo diga *qual* campo falta.
- `tool_called` (`deterministic.py:75`): compara multiconjuntos de nomes (`Counter`), por isso chamar a mesma
  ferramenta duas vezes é diferente de chamar uma vez.
- `forbidden_access` (`deterministic.py:88`): interseção entre as tabelas proibidas do caso e as tabelas que o
  alvo declarou ter acedido. Marcado `security=True`.
- `citations_exist` (`deterministic.py:99`): se o caso exige citação, a ausência é falha (`missing_citation`).
  Cada citação tem de estar em `retrieved_ids`, ou seja, nos chunks que o modelo recebeu.
- `sql_read_only` (`deterministic.py:136`): usa a AST do sqlglot, não expressões regulares. `_sql_problem`
  (`deterministic.py:115`) rejeita erro de parse, mais de um statement, qualquer nó de escrita
  (Insert, Update, Delete, Drop, Alter, Create, Merge) em qualquer parte da árvore, e raízes que não sejam
  SELECT, UNION, INTERSECT ou EXCEPT.

## Porquê esta escolha

- **AST e não regex para SQL.** Uma regex `UPDATE` falha com comentários e subconsultas e dá falsos positivos
  em colunas como `updated_at`. A AST vê a estrutura, não o texto.
- **Motivos estáveis (`sql:write_statement`).** Os relatórios e os gates agregam por motivo. Uma mensagem em
  texto livre não se agrega.
- **`details` sempre preenchido.** Um `passed=False` sem contexto obriga a repetir o caso para perceber porquê.

## Alternativas

- **Validar SQL com uma base de dados real (EXPLAIN num Postgres).** Mais fiel ao motor, mas exige um servidor no
  CI. O projeto não tem Docker nem Postgres local; a AST chega para o critério "só leitura".
- **Lista de permissões de tabelas no próprio SQL.** Fica como evolução do `forbidden_access` com
  `sqlglot.exp.Table`. Hoje o mini RAG declara as tabelas acedidas explicitamente em `accessed_tables`.
- **Só regex para JSON.** Não valida tipos nem enums; o JSON schema é a especificação.

## Como falha

Testes em `tests/test_evaluators.py`:

- `test_json_schema_names_missing_field_after_rename` (campo renomeado),
- `test_json_schema_rejects_wrong_types_and_bad_order_id`,
- `test_sql_read_only_rejects_writes_and_multi_statements` (UPDATE, DELETE, DROP, múltiplos statements, parse error, GRANT),
- `test_sql_read_only_accepts_select_queries`,
- `test_citation_not_in_context_is_rejected`, `test_citations_missing_when_required`.

Limitação conhecida: `sql_read_only` não sabe se um `SELECT` lê dados sensíveis. Isso é tratado pelo
`forbidden_access`, com a lista de tabelas proibidas no caso.

## Perguntas de entrevista

**Porque é que `sql_read_only` não usa uma lista negra de palavras (`UPDATE`, `DROP`)?**
Porque uma lista negra falha com comentários, maiúsculas e subconsultas, e dá falsos positivos em colunas com
nomes parecidos. A AST separa a sintaxe do texto. Uma lista de permissões (só `SELECT`) é mais segura do que uma
lista de proibições.

**O que é uma citação "existente"?**
Um identificador que estava no contexto recuperado para aquela resposta. Não basta existir na base de
conhecimento: se o modelo cita um chunk que não viu, é uma alucinação de fonte, mesmo que o id exista.

**Porque é que cada avaliador devolve `details`?**
Para tornar a falha auditável sem repetir a chamada ao modelo. Uma run guardada tem o motivo e o contexto.
