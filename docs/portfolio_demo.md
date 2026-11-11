# Demonstração guiada — Solar Data Platform

Este roteiro apresenta as funcionalidades existentes a um avaliador técnico, sem modificar os modelos nem depender de dados reais. Tempo e resultados variam conforme o ambiente.

## O que observar

1. Um CSV novo é validado e processado uma única vez.
2. O PostgreSQL registra leituras, quarentena, auditoria e checkpoint.
3. Uma segunda execução do mesmo arquivo é **ignorada**.
4. O dbt constrói e testa o warehouse.
5. O Airflow executa `run_migrations → ingest_raw_csv → dbt_build` e apresenta logs separados de `INFO`, `WARNING` e `ERROR` quando apropriado.

## Preparação

Siga primeiro [o guia de instalação](local_development.md): Python, `.env`, os bancos `postgres` e `postgres_test` e todas as migrations. Não execute comandos que apaguem volumes.

```powershell
python -m pytest -q
```

## A. Demonstrar o processamento incremental

Gere um CSV pequeno e **novo**, escolhendo um identificador que ainda não tenha sido usado (substitua `demo_001` por outro sufixo caso já exista):

```powershell
python scripts/generate_solar_data.py `
  --start-date 2026-11-01 `
  --days 1 `
  --interval-minutes 15 `
  --sites 1 `
  --panels-per-site 2 `
  --gap-pct 1 `
  --duplicate-pct 15 `
  --invalid-pct 25 `
  --seed 42 `
  --output data/generated/solar_portfolio_demo_001.csv

Copy-Item data/generated/solar_portfolio_demo_001.csv `
  data/raw/solar_portfolio_demo_001.csv
python -m scripts.ingest_raw_batches
```

O gerador recusa sobrescrita. A taxa efetiva de duplicatas/quarentena depende da quantidade de linhas e da distribuição de anomalias.

Observe os logs de `solar_portfolio_demo_001.csv`: os contadores de aceitos, quarentenados, duplicatas e, para os limites padrão, eventuais avisos de qualidade. Os avisos são **não bloqueantes**. No caso de erro por nome imutável reutilizado, gere um lote com novo nome; não altere o arquivo antigo.

Repita o comando:

```powershell
python -m scripts.ingest_raw_batches
```

Para o arquivo que acabou de processar, espere `Incremental skip` ou `CSV batch skipped`. O comando percorre **todos** os CSVs presentes em `data/raw`; lotes antigos já registrados também serão ignorados.

## B. Validar transformações dbt

```powershell
python scripts/run_dbt.py build
```

O resultado esperado é que os modelos sejam construídos e seus testes sejam aprovados **se os dados presentes satisfizerem as regras do warehouse**. Falhas reais devem ser investigadas, não ignoradas.

As métricas e as definições dos modelos estão em [data_warehouse.md](data_warehouse.md).

## C. Inspecionar a auditoria SQL

Abra um cliente PostgreSQL conectado à base de desenvolvimento (porta local padrão `5433`, schema operacional `public`) e execute:

```sql
SELECT ingestion_run_id, source_file, status, total_source_rows,
       quarantine_rate_pct, duplicate_rate_pct, processed_at
FROM vw_ingestion_batch_quality
ORDER BY ingestion_run_id DESC
LIMIT 20;
```

A view é baseada em `ingestion_runs` e `processed_files`. As taxas de lotes vazios podem aparecer como `NULL`, e execuções falhas não exibem percentuais enganosos.

## D. Mostrar a orquestração no Airflow

Com Docker Desktop iniciado:

```powershell
docker compose --profile airflow up -d
```

Acesse <http://localhost:8080>, habilite `solar_ingestion_pipeline` caso esteja pausada e dispare uma execução manual.

A ordem esperada:

```text
run_migrations  →  ingest_raw_csv  →  dbt_build
```

Nos logs de `ingest_raw_csv`, verifique o registro dos lotes processados e pulados. Para mostrar **novos** warnings no Airflow, use um lote com nome único ainda não ingerido pelo processamento local; se já tiver checkpoint, será pulado e não emitirá novamente os warnings.

## E. Apresentar resultados no Power BI

Abra o relatório local do projeto e atualize a conexão com as tabelas/views do PostgreSQL conforme [guia local](local_development.md#8-power-bi). Mostre, se disponíveis, as quatro páginas: Visão individual, Comparação, Qualidade e Quarentena.

**Não inferir** geração energética em kWh a partir dos indicadores atuais de potência. Os datasets são sintéticos e as médias não são ponderadas por tempo.

## Evidências que tornam a demo convincente

Use a [lista de capturas reais](portfolio_evidence.md) para registrar o que efetivamente aparece no seu ambiente. Não compartilhe credenciais, tokens, nomes de usuário do sistema ou dados sensíveis nos prints.

## Sobre reprodutibilidade

Os passos acima utilizam código já existente; não constituem um teste de clone limpo executado por esta documentação. Um avaliador deve validar as portas, configurações e disponibilidade dos serviços no próprio ambiente.
