# Exercício controlado: recuperação do PostgreSQL de testes

## Objetivo

Validar que o Airflow registra uma falha temporária de conexão,
faz novas tentativas e consegue recuperar a execução quando o banco
**exclusivo de testes** volta a ficar disponível.

Este exercício utiliza a DAG manual `learning_postgres_recovery`,
não a `solar_ingestion_pipeline`. A consulta executada é apenas
`SELECT current_database(), current_user`; nenhuma leitura solar é
alterada, e nenhum teste do dbt é disparado.

**Nunca interrompa os serviços `postgres` ou `airflow-postgres`
para este exercício.** O primeiro contém os dados de desenvolvimento;
o segundo contém os metadados necessários para o próprio Airflow.

## Preparação (PowerShell)

No diretório raiz, com o banco de testes saudável:

```powershell
git pull origin main
python -m pytest -q tests/test_probe_test_postgres.py
docker compose --profile airflow up -d --force-recreate airflow-scheduler airflow-dag-processor
docker compose ps
```

A recriação dos serviços Airflow é necessária para disponibilizar a
nova variável `TEST_DATABASE_URL` nos processos que executam as tasks.
A URL usa o host interno do Docker Compose `postgres_test`,
distinto do endereço `localhost:5434` utilizado pelos testes Windows.

Se o banco de testes não estiver iniciado, execute
`docker compose up -d postgres_test` antes do teste saudável.

## 1. Cenário saudável

No Airflow, habilite a DAG `learning_postgres_recovery` se ela estiver
pausada, dispare manualmente uma execução e confirme o sucesso do passo
`probe_test_database`. O log deve conter:

```text
Test PostgreSQL connectivity succeeded | service=postgres_test
Step succeeded: Probing isolated PostgreSQL test service (read-only).
```

## 2. Cenário de indisponibilidade e recuperação

Use um terminal para parar **somente** o banco de testes:

```powershell
docker compose stop postgres_test
```

Dispare manualmente uma nova execução da DAG
`learning_postgres_recovery`. A primeira tentativa deve falhar com
um erro de conexão e gerar retry (2 retries, 30 segundos entre tentativas).
O Airflow não pode executar os demais testes de integração enquanto o banco
estiver parado.

Depois de observar a primeira tentativa falha no Airflow, restaure o
serviço **antes da próxima tentativa**:

```powershell
docker compose up -d postgres_test
```

Confirme que o serviço está saudável com `docker compose ps`.
A próxima tentativa elegível deverá registrar sucesso e a DAG terminará
com status verde. Se a janela de retry tiver se esgotado, inicie uma
nova execução manual com o serviço saudável.

### O que registrar

- Número da tentativa que encontrou o serviço indisponível;
- Erro de conexão e log de retry;
- Tentativa de recuperação e log de sucesso;
- Status final da DAG;
- Confirmação de que a DAG principal não foi alterada.

Se a execução falhar definitivamente, verifique o estado do banco de testes,
restaure-o e execute a DAG manual de novo. **Não reinicie o banco de
metadados do Airflow**, pois isso prejudicaria o próprio registro de retries.

## Segurança e limitações

- O script `scripts/probe_test_postgres.py` valida host, nome do banco
  e usuário antes de se conectar; só utiliza consulta de identidade.
- O teste é opt-in: `schedule=None`; não é executado diariamente.
- Falhas de conexão não acionam ingestão, migrations nem gravações de dados.
- O teste não simula transação interrompida durante um COPY; isso exigiria
  outra etapa e instrumentação isolada.
- Não execute `pytest` com o banco de testes desligado.
