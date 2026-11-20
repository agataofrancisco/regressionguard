# Spec Delta

## Purpose

Medir com honestidade se e quando a arbitragem melhora a qualidade face ao seu custo, incluindo os casos em que piora.

## ADDED Requirements

### Requirement: Dataset de participações
O projecto SHALL incluir pelo menos 100 participações sintéticas rotuladas, com datas ambíguas, valores inconsistentes, campos ausentes, valores escritos por extenso e injecção no texto.

#### Scenario: Distribuição de dificuldades
- **WHEN** se consultam as estatísticas do dataset
- **THEN** cada tipo de dificuldade tem casos suficientes para ser reportado em separado

### Requirement: Comparação de estratégias
O runner SHALL comparar sobre o mesmo dataset: modelo barato único, modelo forte único, voto maioritário, arbitragem por evidência e arbitragem + revisão (com revisão simulada a partir dos labels). As métricas são exact match, F1 por campo, cobertura (campos decididos), taxa de erros críticos, latência e custo.

#### Scenario: Tabela accuracy-vs-custo
- **WHEN** a experiência termina
- **THEN** o relatório mostra uma tabela e um gráfico de qualidade vs custo das 5 estratégias, com data, commit e modo

### Requirement: Casos desfavoráveis documentados
O relatório MUST incluir os casos em que a arbitragem aumenta o custo ou o tempo sem ganho e os casos em que dois modelos repetem o mesmo erro, com exemplos.

#### Scenario: Erro correlacionado
- **WHEN** existem casos com erro correlacionado
- **THEN** o relatório mostra quantos foram apanhados pela evidência e quantos escaparam

### Requirement: CI sem custos
A experiência SHALL correr em CI apenas com mocks fixos. Os resultados com modelos reais MUST ser executados manualmente e identificados.

#### Scenario: CI
- **WHEN** a pipeline corre num PR
- **THEN** usa apenas mocks e o relatório indica `provider: mock`
