# Spec Delta

## Purpose

Definir conjuntos de casos de teste curados, versionados e rastreáveis, que são a referência fixa para medir regressões.

## ADDED Requirements

### Requirement: Formato JSONL validado
Cada dataset SHALL ser um ficheiro JSONL com um manifesto (nome, versão, alvo, descrição, autor, data). Cada caso MUST ter `id` estável, `input`, `expected` ou critérios, `category`, `severity` (`critical` ou `normal`) e `source` (de onde veio o label).

#### Scenario: Caso inválido
- **WHEN** um caso não tem `id` ou `category`
- **THEN** a validação falha e indica o ficheiro e o número da linha

#### Scenario: Id duplicado
- **WHEN** dois casos do mesmo dataset partilham o mesmo `id`
- **THEN** a validação falha com `duplicate_case_id`

### Requirement: Versionamento imutável
Cada versão de um dataset MUST ter um hash do conteúdo registado em cada run. Alterar um caso SHALL exigir uma nova versão do dataset, e as comparações MUST usar a mesma versão no baseline e no candidato.

#### Scenario: Datasets diferentes
- **WHEN** se tenta comparar runs feitas com versões diferentes do dataset
- **THEN** a comparação é recusada com `dataset_version_mismatch`

### Requirement: Dimensão mínima do laboratório
O repositório SHALL incluir mais de 80 casos rotulados no total, repartidos pelos dois mini-alvos e por categorias, incluindo casos de segurança (acesso proibido, SQL de escrita, injecção).

#### Scenario: Contagem
- **WHEN** se executa `ai-eval datasets stats`
- **THEN** a saída mostra mais de 80 casos e a distribuição por alvo, categoria e severidade

### Requirement: Guia de contribuição
O projecto SHALL documentar como adicionar um caso golden (formato, como escolher o label, como evitar contaminação e revisão).

#### Scenario: Adicionar caso
- **WHEN** um contribuidor segue o guia e adiciona um caso
- **THEN** `ai-eval datasets validate` passa e o caso aparece na próxima run
