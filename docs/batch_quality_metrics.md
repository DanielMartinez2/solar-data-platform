# Qualidade operacional por lote

A migration `005_create_batch_quality_view.sql` cria a view
`vw_ingestion_batch_quality`, baseada em `ingestion_runs` e
`processed_files`. Cada linha representa uma **tentativa de ingestão**,
inclusive tentativas históricas do modo não incremental.

## Indicadores

- **total_source_rows** = `accepted_count + quarantined_count + duplicate_count`.
  Representa as linhas de dados do arquivo, sem contar o cabeçalho.
- **quarantine_rate_pct** = `100 × quarantined_count / (accepted_count + quarantined_count)`.
  Denominador: registros distintos classificados, sem duplicatas exatas.
- **duplicate_rate_pct** = `100 × duplicate_count / total_source_rows`.
  Denominador: todas as linhas de dados lidas.
- **insertion_rate_pct** = `100 × inserted_readings_count / accepted_count`.
  Essa taxa mede novidades no PostgreSQL, **não** validade dos dados.
  É normal que seja 0% ao reprocessar dados já existentes.

As taxas são arredondadas para duas casas decimais. Se um denominador
for zero, a taxa fica `NULL` (não `0`). Execuções que ainda estão
`running` ou terminaram em `failed` têm contagens e taxas de qualidade
`NULL` porque seus totais de auditoria podem estar incompletos.

`processed_at` só aparece quando a tentativa corresponde a um checkpoint
incremental. Isso permite distinguir ingestões concluídas por checkpoint
das ingestões históricas tradicionais.

## Consulta operacional

```sql
SELECT
    ingestion_run_id, source_file, status,
    total_source_rows, quarantine_rate_pct,
    duplicate_rate_pct, insertion_rate_pct,
    processed_at
FROM vw_ingestion_batch_quality
ORDER BY ingestion_run_id DESC
LIMIT 20;
```

Essa view é **descritiva**. Não bloqueia cargas por percentual de rejeição
e não detecta períodos ausentes, plausibilidade física ou alterações de
arquivos. Esses controles exigem definições próprias de regras e limiares.

## Verificação local

Após atualizar o código, aplicar migrations no banco de desenvolvimento:

```powershell
python scripts/run_migrations.py
```

Aplicar também no banco separado de testes antes de executar testes de
integração:

```powershell
python scripts/run_migrations.py --database-url-env TEST_DATABASE_URL
python -m pytest -q tests/test_pipeline_integration.py
```
