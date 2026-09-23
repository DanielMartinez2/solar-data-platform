# Solar Data Platform

Plataforma de dados para ingestão, validação, armazenamento e análise de medições de geração solar, desenvolvida com Python, PostgreSQL e dbt.

O projeto lê medições fotovoltaicas a partir de arquivos CSV, valida e normaliza os dados, identifica duplicatas, conflitos e registros inválidos, persiste separadamente as leituras aceitas e os registros em quarentena e registra auditoria de cada execução de ingestão.

Após a ingestão, o dbt transforma os dados válidos em modelos dimensionais e indicadores analíticos de potência e cobertura, preparando a base para consumo posterior no Power BI.

## Funcionalidades implementadas

### Ingestão e validação

- Leitura de arquivos CSV e verificação do cabeçalho obrigatório.
- Validação de timestamps com fuso horário.
- Conversão e validação de campos numéricos.
- Aplicação de regras de domínio.
- Agrupamento pela chave natural `(timestamp, site_id, panel_id)`.
- Identificação de duplicatas exatas.
- Identificação de versões distintas da mesma chave natural.
- Quarentena simétrica dos registros envolvidos em conflitos.
- Preservação do registro bruto e dos erros de validação em colunas `JSONB`.
- Classificação da ingestão em:
  - `accepted`;
  - `quarantined`;
  - `skipped_duplicate_rows`.

### Persistência e auditoria

- Persistência idempotente com `ON CONFLICT DO NOTHING`.
- Armazenamento das medições válidas em `solar_readings`.
- Armazenamento dos registros rejeitados em `quarantined_readings`.
- Auditoria das execuções em `ingestion_runs`.
- Registro de:
  - quantidade de registros aceitos;
  - quantidade efetivamente inserida;
  - quantidade em quarentena;
  - quantidade efetivamente inserida na quarentena;
  - duplicatas detectadas;
  - status da execução;
  - mensagem de erro, quando aplicável.
- Transação atômica para persistência das medições aceitas, registros em quarentena e finalização da execução.
- Registro separado de falha caso a transação principal seja revertida.

### Dados sintéticos

- Gerador parametrizável de dados solares sintéticos.
- Configuração por linha de comando de:
  - período;
  - frequência das medições;
  - número de instalações;
  - número de painéis por instalação;
  - percentual de lacunas;
  - percentual de duplicatas;
  - percentual de registros inválidos;
  - percentual de conflitos;
  - semente aleatória.
- Geração reprodutível dos dados.
- Criação automática de manifesto JSON com parâmetros, contagens e checksum SHA-256.
- Simulação simplificada da curva diária de irradiância e potência.
- Utilização de um modelo padrão de módulo fotovoltaico em todas as instalações simuladas.

### Data Warehouse

- Transformações com dbt.
- Camada de staging.
- Tabela de fatos de medições solares.
- Dimensão de painéis.
- Agregações por instalação e por período.
- Indicadores horários e diários.
- Indicador de cobertura diária das medições.
- Configuração de cobertura por instalação utilizando dbt seed.
- Testes de reconciliação entre staging, fatos e marts.
- Testes de integridade, unicidade, consistência e limites dos indicadores.

## Tecnologias

- Python 3.12+
- PostgreSQL 18
- Docker Compose
- Psycopg 3
- python-dotenv
- pytest
- dbt Core
- dbt-postgres

## Estrutura principal

```text
solar-data-platform/
├── compose.yaml
├── .env.example
├── requirements.txt
├── README.md
├── data/
│   ├── raw/
│   │   └── solar_readings.csv
│   └── generated/
├── database/
│   ├── schema.sql
│   └── migrations/
├── docs/
│   └── data_warehouse.md
│   |__ README_GENERATOR.md
├── scripts/
│   ├── generate_solar_data.py
│   └── run_dbt.py
├── src/
│   ├── database.py
│   ├── inspect_csv.py
│   └── validate_readings.py
├── tests/
│   ├── fixtures/
│   ├── test_database.py
│   ├── test_generate_solar_data.py
│   ├── test_pipeline_integration.py
│   └── test_validate_readings.py
└── warehouse/
    ├── dbt_project.yml
    ├── profiles.yml
    ├── models/
    │   ├── staging/
    │   └── marts/
    ├── seeds/
    └── tests/