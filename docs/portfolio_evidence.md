# Evidências visuais do portfólio

Este guia define quais capturas **reais** do ambiente local enriquecem o README. Nenhuma captura é gerada automaticamente ou presumida existente.

## Capturas recomendadas

| Arquivo sugerido | Fonte | O que deve ficar visível |
|---|---|---|
| `docs/assets/powerbi-overview.png` | Power BI Desktop — Visão individual | Indicadores, curva horária e título do relatório |
| `docs/assets/powerbi-quality.png` | Power BI Desktop — Qualidade | Cobertura, lacunas, inválidas e conflitos |
| `docs/assets/airflow-pipeline.png` | Interface Airflow — DAG `solar_ingestion_pipeline` | As três tasks e seus estados de sucesso |
| `docs/assets/airflow-warning-log.png` (opcional) | Logs Airflow — ingest_raw_csv | Um `WARNING` real de qualidade em lote novo |

Evite capturas de painéis com dados reais, segredos, nomes privados, tokens,
`DATABASE_URL` ou caminhos que revelem informações pessoais.

## Como coletar

1. Execute e valide a pipeline em uma DAG run com sucesso.
2. Amplie apenas a região relevante da tela, com títulos e unidades legíveis.
3. Exporte ou capture imagens em PNG, com boa resolução.
4. Salve as imagens na pasta `docs/assets/` e faça commit na branch da PR de apresentação.
5. Atualize o README para referenciar apenas os arquivos **existentes** e verificáveis.

Exemplo de Markdown a usar **após adicionar a imagem real**:

```markdown
![Airflow — pipeline solar com migrations, ingestão incremental e dbt concluídos](docs/assets/airflow-pipeline.png)
```

O mesmo vale para as páginas Power BI. Não adicionar links de imagem apontando
para arquivos inexistentes.

## Resultados analíticos

Para apresentar o cenário principal, utilize a mesma configuração do
dashboard documentado em agosto de 2026 (30 dias, 10 instalações e 10 painéis por
instalação). A demonstração incremental sugerida em
[portfolio_demo.md](portfolio_demo.md) usa uma data fora do período do seed
de cobertura do exemplo principal; ela **não** constitui uma nova medição
de cobertura desse dashboard.

Se desejar demonstrar cobertura para novas datas, uma etapa posterior deve
acrescentar uma configuração de cobertura correspondente no seed e validar
os marts e testes dbt, em PR separada.

## Antes de publicar

- Confirme que todas as capturas são do programa em execução e foram realmente produzidas.
- Confira se a data e a instalação exibidas fazem sentido com o dataset.
- Não publique senhas nem IDs de credenciais.
- Confirme que as imagens abrem no preview do GitHub.
- Se preferir não publicar um arquivo de relatório Power BI, disponibilize pelo menos as capturas do dashboard para permitir avaliação visual.
