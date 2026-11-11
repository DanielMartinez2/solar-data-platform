# Exercício de resiliência: timeouts e concorrência no Airflow

Esta prática utiliza somente DAGs **manuais e isoladas**:
- `learning_task_timeout`
- `learning_dag_concurrency`

Ambas usam somente `time.sleep` e logs: **não acessam bancos, não executam
migrations, não alteram CSVs e não executam dbt**. O workflow principal
`solar_ingestion_pipeline` permanece inalterado.

## Preparação

Após revisão da PR, checks da CI e merge:

```powershell
git pull origin main
python -m pytest -q
docker compose --profile airflow ps
```

Como as DAGs estão no volume `./airflow/dags:/opt/airflow/dags`, elas
deverão aparecer quando o processador de DAGs recarregar os arquivos.
Caso não apareçam, verifique o estado do `airflow-dag-processor` e os
erros de importação das DAGs.

## Cenário A — Timeout de task (falha esperada)

Ative `learning_task_timeout` caso esteja pausada. Execute manualmente
com a configuração padrão ou:

```json
{"hold_seconds": 15}
```

A task tem `execution_timeout=5s` e `retries=0`. Ela tenta dormir
por 15s e deve ser interrompida por um timeout do Airflow. Verifique:
- Log com `Timeout drill | configured_seconds=15`;
- Exceção indicando limite de tempo de execução;
- Task e DAG finalizadas em `FAILED`.

**Controle positivo:** em uma nova execução, use:

```json
{"hold_seconds": 2}
```

A task deve terminar antes de 5s e a DAG finalizar em `SUCCESS`.
O tempo total pode incluir overhead de inicialização; se houver variações
no ambiente, observe o tempo efetivo reportado pelo Airflow.

## Cenário B — Controle de concorrência

Ative `learning_dag_concurrency`. Esta DAG tem
`max_active_runs=1`; cada execução mantém uma task ativa por cerca de
45 segundos (valor padrão). Execute **duas vezes**, com poucos segundos
de intervalo, ambas com:

```json
{"hold_seconds": 45}
```

Na interface Grid / DAG Runs:
- Primeira execução deve estar `running`.
- Segunda execução deve aguardar para ser iniciada (em geral em `queued`).
- Apenas após o término da primeira a segunda deve iniciar a task.
- As duas devem acabar em `SUCCESS`, sem sobreposição dos intervalos
  **da DAG**. Compare os `run_id` e horários de início e conclusão nos
  logs `Resilience drill started/completed`.

**Atenção:** `max_active_runs=1` restringe execuções da *mesma DAG*;
não é um lock global e não bloqueia DAGs diferentes entre si.
O agendamento da segunda run pode ter um pequeno atraso além dos 45s.

## O que registrar

1. DAG timeout: log da exceção de timeout e resultado do controle positivo.
2. Concorrência: horários / `run_id` das duas execuções e evidência de
   que os períodos ativos não se sobrepõem.
3. Resultado da suíte `python -m pytest -q`.

## Limites do experimento

- O timeout é deliberadamente curto (5s) para observação e sem retries.
- O exercício não simula um processo externo resistente a sinais de
  terminação, nem uma transação de banco interrompida.
- O limite de concorrência de `solar_ingestion_pipeline` já era
  `max_active_runs=1`; este teste valida o mecanismo com uma DAG segura.
- Nenhuma tarefa é agendada automaticamente (`schedule=None`).
