# Exercício de resiliência: falha controlada em um teste dbt

Esta prática usa a DAG **manual** `learning_dbt_quality_failure`. Ela executa
um projeto dbt independente, armazenado em `scripts/dbt_resilience`, contra
**somente** o banco de testes `postgres_test`.

A consulta do teste é um `SELECT` de uma linha sintética. No dbt, testes
singulares falham quando retornam uma ou mais linhas. A flag de execução
altera a condição para que a consulta retorne zero linhas no cenário de
sucesso.

**Não use a DAG principal `solar_ingestion_pipeline` para o exercício.**
Nenhum modelo, tabela ou dado solar é alterado por este teste.

## Preparação

Depois de revisar a PR e realizar o merge:

```powershell
git pull origin main
docker compose up -d postgres_test
python -m pytest -q
docker compose --profile airflow up -d --force-recreate airflow-scheduler airflow-dag-processor
```

Recriar os serviços Airflow aplica a nova variável
`DBT_ENV_SECRET_TEST_POSTGRES_PASSWORD`. O nome da variável é requerido
pelo dbt, e seu valor vem de `POSTGRES_TEST_PASSWORD` do arquivo `.env`.

## 1. Falha intencional

No Airflow, habilite a DAG `learning_dbt_quality_failure` se necessário,
e faça uma execução manual com a configuração padrão, ou:

```json
{"allow_pass": false}
```

O teste singular `intentional_quality_failure` retornará uma linha:
o dbt deverá reportar **FAIL** e terminar com código diferente de zero.
O Airflow registrará **ERROR**, agendará duas novas tentativas (30 segundos
entre elas) e, como a condição não muda durante a mesma execução, a DAG
deverá terminar **FAILED** depois das tentativas.

Isso é **esperado**: um retry não corrige uma violação de qualidade
determinística.

## 2. Condição corrigida — nova execução

Dispare **outra execução manual** da mesma DAG, desta vez com:

```json
{"allow_pass": true}
```

O teste dbt retorna zero linhas inválidas. A execução deve terminar
**SUCCESS**, sem precisar de retries.

Essa diferença demonstra que erros de qualidade propagam falha, enquanto
a correção da condição permite o sucesso. Ao contrário do exercício de
PostgreSQL, não se trata de uma recuperação automática durante o mesmo run.

## Conferências

- Primeira execução: `dbt test` reporta uma falha; subprocesso retorna
  código não zero; Airflow registra `ERROR`, retries e status `FAILED`.
- Segunda execução: `dbt test` passa; Airflow registra `Step succeeded`
  e status `SUCCESS`.
- `solar_ingestion_pipeline` permanece inalterada.
- `postgres` e `airflow-postgres` não precisam ser desligados.

## Segurança e escopo

O runner valida host `postgres_test`, usuário e nome do banco com a
mesma proteção usada pelo exercício anterior. O projeto dbt usa apenas
`SELECT` sobre valores constantes; não cria nem modifica tabelas de
desenvolvimento. A execução é opt-in (`schedule=None`).
