# Solar Data Platform — guia de desenvolvimento local

Comandos testáveis no **PowerShell** a partir da raiz do repositório.
Este ambiente de desenvolvimento usa Docker Desktop, Python e PostgreSQL.
Para a arquitetura e os contratos de dados, consulte [architecture.md](architecture.md).

## Pré-requisitos

- Python 3.12+ e Docker Desktop com Docker Compose;
- Portas livres `5433`, `5434` e `8080` (ou portas alteradas em `.env`);
- Power BI Desktop para abrir/conectar o relatório, se desejado.

## 1. Ambiente Python

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copie o exemplo de ambiente **somente se ainda não possuir** seu `.env`:

```powershell
Copy-Item .env.example .env
```

Edite as credenciais para seu ambiente. **Não versione `.env`**, senhas ou tokens. Os segredos Airflow do exemplo são apenas para desenvolvimento local.

## 2. Bancos e migrations

```powershell
docker compose up -d postgres postgres_test
docker compose ps
python scripts/run_migrations.py
python scripts/run_migrations.py --database-url-env TEST_DATABASE_URL
```

O runner aplica migrations novas em ordem e verifica checksum das versões antigas.
**Nunca edite uma migration já aplicada.** Para uma mudança de schema,
crie uma nova migration.

Em instalações antigas com schema criado manualmente, `--baseline-through`
existe para uso excepcional; não o use em banco vazio ou sem conferir
correspondência do schema. Consulte os comentários do runner antes de baselinar.

## 3. Testar a aplicação

```powershell
python -m pytest -q
```

`pytest.ini` limita a busca a `tests/`, evitando links de log do Airflow
incompatíveis com a coleta de arquivos no Windows. Os testes de integração
exigem o banco de testes acessível e seu schema aplicado. `tests/conftest.py`
verifica isolamento e identidade do banco antes de redirecionar as conexões.

## 4. Ingestão local

CSV demonstrativo pré-existente:

```powershell
python -m src.database --csv-path data/raw/solar_readings.csv --incremental
```

Processar **todos** os CSVs diretamente em `data/raw` de maneira incremental:

```powershell
python -m scripts.ingest_raw_batches
```

O lote é identificado pelo **nome do arquivo** e pelo seu SHA-256.
Mesma origem com mesmo checksum → pulado; mesmo nome com outro conteúdo →
erro. Para novo lote, gere ou copie um **novo** nome de arquivo; não altere
um arquivo já checkpointado.

Para gerar dados sintéticos em uma pasta separada:

```powershell
python scripts/generate_solar_data.py `
  --start-date 2026-11-01 `
  --days 1 `
  --interval-minutes 15 `
  --sites 1 `
  --panels-per-site 2 `
  --gap-pct 1 `
  --duplicate-pct 1 `
  --invalid-pct 1 `
  --output data/generated/solar_demo_2026-11-01.csv
```

O gerador também cria um manifesto `.manifest.json` e impede sobrescrita.
Se quiser ingerir esse lote, **copie apenas o CSV** para `data/raw`
(com nome novo), pois o descobridor automático só procura `*.csv` nessa
pasta, sem recursão:

```powershell
Copy-Item data/generated/solar_demo_2026-11-01.csv data/raw/solar_demo_2026-11-01.csv
python -m scripts.ingest_raw_batches
```

Evite reutilizar esse nome em execuções com parâmetros diferentes.

## 5. Transformações dbt

Na raiz do repositório, com PostgreSQL de desenvolvimento funcionando:

```powershell
python scripts/run_dbt.py build
```

O wrapper carrega o `.env` e fornece a senha do PostgreSQL ao dbt.
As configurações e os modelos ficam em `warehouse/`. O comando `dbt build`
constrói recursos do warehouse e executa os testes associados.

## 6. Airflow completo (perfil opcional)

```powershell
docker compose --profile airflow build
docker compose --profile airflow up airflow-init
docker compose --profile airflow up -d
docker compose --profile airflow ps
```

Interface local: <http://localhost:8080>. A configuração de autenticação
simples e os segredos demonstrativos **não são adequados para produção**.

A DAG `solar_ingestion_pipeline` é agendada diariamente para **09:00**
(`America/Sao_Paulo`) e normalmente começa pausada no ambiente local.
Na primeira execução, habilite a DAG pela interface, se necessário, e
dispare-a manualmente para validar.

```powershell
docker compose --profile airflow exec airflow-scheduler airflow dags list
docker compose --profile airflow exec airflow-scheduler airflow dags trigger solar_ingestion_pipeline
```

Pipeline:

```text
run_migrations -> ingest_raw_csv -> dbt_build
```

Para alterações na imagem ou em variáveis de ambiente, **reconstrua ou
recrie** os serviços afetados conforme necessário. Para mudanças em arquivos
DAG/scripts, o Docker Compose já usa volumes montados; aguarde o parser
redescobrir as DAGs.

### Avisos operacionais (não bloqueantes)

```dotenv
SOLAR_MAX_QUARANTINE_PCT=20
SOLAR_MAX_DUPLICATE_PCT=10
```

Os percentuais são comparados com os indicadores arredondados da
`vw_ingestion_batch_quality`; uma taxa **acima** do limite produz
`WARNING`, assim como um lote vazio. Igualdade com o limite não avisa.
Os alertas só são avaliados para **novos** arquivos processados com sucesso.
Alterações em `.env` usadas pelo Airflow exigem recriar o serviço executor
que recebe as variáveis.

## 7. Diagnóstico e recuperação

### Verificar serviços e logs

```powershell
docker compose --profile airflow ps
docker compose --profile airflow logs --tail 100 airflow-scheduler
```

Quando uma task falhar, verifique o **run_id**, `task_id`, a tentativa
(`try_number`), o `exit_code` do subprocesso e o primeiro erro de
conexão/dbt/validação nos logs.

### SQL para diagnosticar ingestões

```sql
SELECT ingestion_run_id, source_file, status, total_source_rows,
       quarantine_rate_pct, duplicate_rate_pct, processed_at
FROM vw_ingestion_batch_quality
ORDER BY ingestion_run_id DESC
LIMIT 20;
```

Para a semântica das métricas, consulte [batch_quality_metrics.md](batch_quality_metrics.md).

### Exercícios de resiliência isolados

- [PostgreSQL de testes indisponível e recuperação por retry](postgres_recovery_drill.md)
- [Teste dbt intencionalmente inválido e posterior execução correta](dbt_quality_failure_drill.md)
- [Timeout e controle de DAG runs concorrentes](airflow_timeout_concurrency_drill.md)

As DAGs de aprendizado têm `schedule=None` e não são necessárias à
execução normal do pipeline.

### Preservação do ambiente

`docker compose stop` interrompe os serviços preservando volumes.
**Não use `docker compose down -v`** se pretende manter os bancos locais,
pois `-v` remove os volumes nomeados.

## 8. Power BI

A saída da etapa dbt são tabelas e views de `analytics` no PostgreSQL.
Configure a conexão do Power BI Desktop com a base de desenvolvimento
(`localhost:5433` por padrão) e credenciais do seu `.env`.
O modelo/report local pode exigir configuração da origem de dados;
a documentação não pressupõe um link público ou atualização automática
do dashboard.

Veja a descrição das métricas em [data_warehouse.md](data_warehouse.md).
