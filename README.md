# Solar Data Platform

Pipeline de dados de geração solar desenvolvido em Python e PostgreSQL. O projeto lê medições de um CSV bruto, valida seus campos, identifica duplicatas e conflitos por chave natural e persiste separadamente as leituras aceitas e os registros em quarentena.

## Funcionalidades implementadas

- Leitura de CSV e verificação do cabeçalho obrigatório.
- Validação de timestamps com fuso horário, campos numéricos e regras de domínio.
- Agrupamento pela chave natural `(timestamp, site_id, panel_id)`.
- Identificação de duplicatas exatas; versões distintas da mesma chave vão para quarentena com referências de conflito.
- Preservação do registro bruto e dos erros de validação em colunas `JSONB`.
- Persistência idempotente com `ON CONFLICT DO NOTHING` e rollback dentro de cada operação de inserção.
- Testes automatizados com pytest, incluindo testes de integração com PostgreSQL.

## Tecnologias

Python 3.12+, PostgreSQL 18, Docker Compose, Psycopg 3, python-dotenv e pytest.

## Estrutura principal

```text
solar-data-platform/
├── compose.yaml
├── .env.example
├── requirements.txt
├── README.md
├── data/raw/solar_readings.csv
├── database/
│   ├── schema.sql
│   └── migrations/
├── src/
│   ├── database.py
│   ├── inspect_csv.py
│   └── validate_readings.py
└── tests/
    └── fixtures/
```

## Preparar o ambiente (PowerShell)

Execute os comandos a partir da raiz do projeto.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copie `.env.example` para `.env` **somente se ainda não existir um `.env`**. Edite a senha e mantenha `POSTGRES_PASSWORD` e `DATABASE_URL` consistentes. O `.env` deve permanecer fora do Git.

```powershell
Copy-Item .env.example .env
```

O projeto usa a porta `5433` no host para não conflitar com uma instalação local do PostgreSQL que utilize `5432`. Inicie o banco:

```powershell
docker compose up -d
docker compose ps
```

Em uma instalação **nova**, `database/schema.sql` precisa criar **ambas** as tabelas (`solar_readings` e `quarantined_readings`). Em um volume que já exista, scripts de `/docker-entrypoint-initdb.d/` não são executados novamente; nesse caso, aplique as migrations pendentes manualmente, conforme necessário. Não use `docker compose down -v` se quiser preservar os dados.

## Executar o pipeline

```powershell
python -m src.database
```

A carga separa os resultados em `accepted`, `quarantined` e `skipped_duplicate_rows`. As duas rotinas de inserção são individualmente transacionais; **a gravação nas duas tabelas ainda não constitui uma única transação conjunta**.

## Executar testes

Com o PostgreSQL iniciado e o `.env` configurado:

```powershell
python -m pytest -v
```

Os testes de integração acessam um banco de desenvolvimento e utilizam identificadores próprios de teste, removendo seus registros ao final. Evite executar a suíte contra um banco de produção.

## Próximas etapas

Automatizar testes no GitHub Actions, evoluir o gerenciamento de migrations e preparar as etapas de transformação, análise e orquestração dos dados.

## Segurança

Não faça commit de `.env`, senhas ou URLs com credenciais reais. Versione somente `.env.example`, com valores de exemplo.
