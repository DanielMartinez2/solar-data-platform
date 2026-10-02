# Solar Data Platform

Plataforma de dados para ingestão, validação, armazenamento, transformação e análise de medições de geração solar.

O projeto foi desenvolvido com Python, PostgreSQL, dbt e Power BI e implementa um pipeline de dados de ponta a ponta: desde a leitura de arquivos CSV até a construção de indicadores analíticos e dashboards.

A plataforma valida medições fotovoltaicas, identifica duplicatas, conflitos e registros inválidos, mantém registros problemáticos em quarentena, audita as execuções de ingestão e transforma os dados válidos em modelos analíticos para consumo no Power BI.

> Os dados utilizados atualmente para demonstração são sintéticos e foram gerados exclusivamente para desenvolvimento, testes e portfólio.

---

## Visão geral da arquitetura

```text
CSV bruto / dados sintéticos
          │
          ▼
Python
├── inspeção
├── validação
├── normalização
├── deduplicação
└── detecção de conflitos
          │
          ├──────────────► Quarentena
          │                PostgreSQL / JSONB
          │
          ▼
Medições válidas
PostgreSQL
          │
          ▼
dbt
├── staging
├── dimensão
├── fatos
├── marts
├── cobertura
└── qualidade dos dados
          │
          ▼
Power BI
├── análise individual
├── comparação entre instalações
├── qualidade dos dados
└── detalhamento da quarentena
```

---

## Principais funcionalidades

### Ingestão e validação

- Leitura de arquivos CSV.
- Validação do cabeçalho obrigatório.
- Validação de timestamps com fuso horário.
- Conversão e validação de campos numéricos.
- Aplicação de regras de domínio.
- Normalização das medições.
- Agrupamento pela chave natural:

```text
(timestamp, site_id, panel_id)
```

- Identificação de duplicatas exatas.
- Identificação de versões diferentes da mesma chave natural.
- Quarentena simétrica dos registros envolvidos em conflitos.
- Preservação do registro bruto e dos erros em `JSONB`.
- Classificação da ingestão em:
  - `accepted`;
  - `quarantined`;
  - `skipped_duplicate_rows`.

### Persistência e auditoria

- Persistência idempotente com `ON CONFLICT DO NOTHING`.
- Armazenamento das medições válidas em `solar_readings`.
- Armazenamento dos registros problemáticos em `quarantined_readings`.
- Auditoria das execuções em `ingestion_runs`.
- Registro de:
  - registros aceitos;
  - registros efetivamente inseridos;
  - registros em quarentena;
  - registros efetivamente inseridos na quarentena;
  - duplicatas detectadas;
  - status da execução;
  - mensagens de erro.
- Transação atômica para:
  - medições aceitas;
  - quarentena;
  - finalização da execução.
- Registro separado da falha caso a transação principal seja revertida.

### Gerador de dados sintéticos

- Gerador parametrizável em Python.
- Configuração por linha de comando de:
  - data inicial;
  - duração;
  - frequência das medições;
  - quantidade de instalações;
  - quantidade de painéis;
  - percentual de lacunas;
  - percentual de duplicatas;
  - percentual de registros inválidos;
  - percentual de conflitos;
  - semente aleatória.
- Geração reprodutível.
- Criação automática de manifesto JSON.
- Cálculo de checksum SHA-256.
- Simulação simplificada de irradiância e potência ao longo do dia.
- Introdução controlada de:
  - lacunas;
  - duplicatas exatas;
  - valores inválidos;
  - conflitos de chave natural.

### Data Warehouse

- Transformações com dbt.
- Camada de staging.
- Dimensão de painéis.
- Tabela de fatos de medições solares.
- Agregações por instalação e por período.
- Indicadores horários e diários.
- Indicador de cobertura diária das medições.
- Configuração de cobertura por instalação utilizando dbt seed.
- Indicadores de qualidade dos dados.
- Separação entre:
  - lacunas;
  - medições inválidas;
  - conflitos.
- Detalhamento dos erros armazenados em quarentena por:
  - tipo de erro;
  - campo afetado;
  - instalação;
  - dia.
- Testes de reconciliação entre staging, fatos e marts.
- Testes de integridade, unicidade, consistência e limites dos indicadores.

### Dashboard Power BI

O projeto inclui um dashboard desenvolvido em Power BI para consumo dos modelos analíticos armazenados no PostgreSQL.

O relatório possui quatro páginas:

1. **Visão individual**
   - potência média diária;
   - pico de potência observado;
   - cobertura diária;
   - curva horária de potência;
   - evolução da cobertura diária;
   - evolução da potência média diária.

2. **Comparação**
   - quantidade de instalações analisadas;
   - cobertura geral;
   - medições válidas;
   - medições esperadas;
   - potência média por instalação;
   - cobertura acumulada por instalação.

3. **Qualidade**
   - medições ausentes ou rejeitadas;
   - lacunas;
   - medições inválidas;
   - conflitos;
   - perdas por instalação;
   - composição das perdas por causa;
   - evolução diária das perdas de qualidade.

4. **Quarentena**
   - erros de validação por tipo;
   - erros por campo afetado;
   - evolução diária dos erros;
   - distribuição dos erros por instalação.

A navegação entre as páginas é realizada por um navegador de páginas integrado ao relatório.

---

## Tecnologias

- Python 3.12+
- PostgreSQL 18
- Docker Compose
- Psycopg 3
- python-dotenv
- pytest
- dbt Core
- dbt-postgres
- Power BI Desktop
- DAX

---

## Estrutura do projeto

```text
solar-data-platform/
├── compose.yaml
├── .env.example
├── requirements.txt
├── README.md
├── solar_data.pdf
│
├── data/
│   ├── raw/
│   │   └── solar_readings.csv
│   └── generated/
│
├── database/
│   ├── schema.sql
│   └── migrations/
│
├── docs/
│   ├── data_warehouse.md
│   └── README_GENERATOR.md
│
├── scripts/
│   ├── generate_solar_data.py
│   └── run_dbt.py
│
├── src/
│   ├── database.py
│   ├── inspect_csv.py
│   └── validate_readings.py
│
├── tests/
│   ├── fixtures/
│   ├── test_database.py
│   ├── test_generate_solar_data.py
│   ├── test_pipeline_integration.py
│   └── test_validate_readings.py
│
└── warehouse/
    ├── dbt_project.yml
    ├── profiles.yml
    ├── models/
    │   ├── staging/
    │   └── marts/
    ├── seeds/
    └── tests/
```

Os arquivos em `data/generated/` são reproduzíveis pelo gerador e não precisam ser versionados no Git.

---

# Quick Start

## 1. Criar o ambiente Python

Execute os comandos a partir da raiz do projeto.

### PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 2. Configurar variáveis de ambiente

Copie `.env.example` para `.env` apenas se ainda não existir:

```powershell
Copy-Item .env.example .env
```

Configure as credenciais do PostgreSQL.

O arquivo `.env` deve permanecer fora do Git.

## 3. Iniciar os bancos PostgreSQL

```powershell
docker compose up -d
docker compose ps
```

Por padrão:

| Ambiente | Porta |
|---|---:|
| Desenvolvimento | `5433` |
| Testes | `5434` |

Isso evita conflito com instalações locais do PostgreSQL que utilizem a porta `5432`.

Para interromper os contêineres preservando os volumes:

```powershell
docker compose stop
```

Evite:

```powershell
docker compose down -v
```

caso queira preservar os dados.

---

## Inicialização e migrations

Em uma instalação nova, `database/schema.sql` cria as tabelas iniciais do banco.

Em volumes já existentes, scripts de `/docker-entrypoint-initdb.d/` não são executados novamente.

Nesse caso, migrations pendentes devem ser aplicadas manualmente.

---

# Executar o pipeline de ingestão

O arquivo padrão pode ser processado com:

```powershell
python -m src.database
```

Fluxo da ingestão:

1. leitura do CSV;
2. validação;
3. normalização;
4. identificação de duplicatas e conflitos;
5. classificação dos registros;
6. início da auditoria;
7. persistência das medições válidas;
8. persistência dos registros em quarentena;
9. conclusão da execução.

Em caso de erro, a transação principal é revertida e a execução é posteriormente registrada como `failed`.

---

# Tabelas operacionais

## `solar_readings`

Armazena as medições válidas.

A chave primária é composta por:

```text
(timestamp, site_id, panel_id)
```

## `quarantined_readings`

Armazena registros inválidos ou conflitantes, preservando:

- arquivo de origem;
- número da linha;
- registro bruto em JSONB;
- lista estruturada de erros em JSONB;
- data da quarentena.

## `ingestion_runs`

Armazena o histórico das execuções do pipeline, incluindo:

- arquivo de origem;
- início;
- término;
- status;
- registros classificados;
- registros efetivamente inseridos;
- registros em quarentena;
- duplicatas;
- mensagens de erro.

---

# Dados sintéticos

## Gerar um conjunto de dados

Exemplo:

```powershell
python scripts/generate_solar_data.py `
  --start-date 2026-08-01 `
  --days 30 `
  --interval-minutes 15 `
  --sites 10 `
  --panels-per-site 10 `
  --gap-pct 1 `
  --duplicate-pct 0.5 `
  --invalid-pct 0.5 `
  --conflict-pct 0.1
```

O gerador produz:

- arquivo CSV;
- manifesto JSON;
- checksum SHA-256;
- contagens das anomalias introduzidas.

---

## Conjunto principal utilizado no dashboard

O conjunto principal é inteiramente sintético e cobre o período:

```text
01/08/2026 a 30/08/2026
```

Configuração:

- 30 dias;
- medições a cada 15 minutos;
- 10 instalações;
- 10 painéis por instalação;
- 100 painéis simulados;
- 96 horários esperados por painel por dia;
- 288.000 medições teóricas.

### Anomalias configuradas

| Tipo | Percentual |
|---|---:|
| Lacunas | 1% |
| Duplicatas exatas | 0,5% |
| Registros inválidos | 0,5% |
| Conflitos | 0,1% |

### Resultado do processamento

```text
Accepted: 283392
Quarantined: 2016
Duplicates: 1440
```

Tempo observado durante a ingestão completa no ambiente de desenvolvimento:

```text
187.95 segundos
```

Esse valor é apenas uma referência do ambiente utilizado durante o desenvolvimento e não representa benchmark de produção.

---

# Modelo fotovoltaico utilizado na simulação

Todos os painéis sintéticos utilizam como referência o módulo:

```text
Canadian Solar HiKu6 CS6W-550MS
```

O gerador utiliza parâmetros elétricos do módulo para produzir valores coerentes de:

- irradiância;
- temperatura;
- tensão;
- corrente;
- potência.

A simulação é intencionalmente simplificada e não deve ser utilizada como ferramenta de previsão real de geração fotovoltaica ou avaliação de desempenho de sistemas reais.

---

# Data Warehouse

O projeto utiliza dbt para transformar as medições validadas em modelos analíticos.

## Principais modelos

```text
stg_solar_readings
dim_panels
fct_solar_readings
mart_site_performance
mart_site_power_timeseries
mart_site_hourly_power
mart_site_daily_power
mart_site_daily_coverage
mart_site_daily_data_quality
mart_quarantine_error_breakdown
```

---

## `stg_solar_readings`

Padroniza as medições aceitas e calcula a potência instantânea:

```text
power_w = voltage_v × current_a
```

---

## `dim_panels`

Representa os painéis observados nas medições válidas.

A identificação de um painel utiliza a chave de negócio:

```text
(site_id, panel_id)
```

O modelo também registra:

- primeiro instante observado;
- último instante observado.

Esses valores representam a presença do painel nos dados e não necessariamente seu ciclo de instalação física.

---

## `fct_solar_readings`

Tabela de fatos com uma linha por:

```text
(measured_at, site_id, panel_id)
```

Preserva as medições válidas utilizadas na camada analítica.

---

## `mart_site_performance`

Resume indicadores gerais por instalação.

Inclui informações como:

- quantidade de painéis observados;
- quantidade de leituras;
- primeiro e último instante;
- potência média;
- potência mínima;
- potência máxima.

---

## `mart_site_power_timeseries`

Agrega a potência observada dos painéis válidos de uma instalação em cada instante.

A potência observada representa apenas os painéis que possuem uma medição válida naquele momento.

---

## `mart_site_hourly_power`

Produz indicadores horários por instalação:

- quantidade de instantes observados;
- potência média;
- potência máxima.

---

## `mart_site_daily_power`

Produz indicadores diários por instalação:

- quantidade de instantes;
- quantidade de contribuições dos painéis;
- potência média;
- potência máxima.

---

## `mart_site_daily_coverage`

Compara a quantidade de medições válidas com a quantidade esperada por instalação e dia.

---

## `mart_site_daily_data_quality`

Decompõe as perdas de cobertura em:

- lacunas;
- registros inválidos;
- conflitos.

---

## `mart_quarantine_error_breakdown`

Detalha os erros de validação armazenados na quarentena por:

- instalação;
- data;
- tipo de erro;
- campo afetado.

Conflitos são tratados separadamente da análise dos erros de campo.

---

# Cobertura das medições

A cobertura representa a completude dos registros válidos.

Para cada instalação e dia:

```text
medicoes_esperadas =
    quantidade_de_paineis
    × horarios_esperados_por_dia
```

e:

```text
cobertura_pct =
    100
    × medicoes_validas
    / medicoes_esperadas
```

A configuração utilizada para esse cálculo é mantida em:

```text
warehouse/seeds/solar_coverage_config.csv
```

Isso permite representar diferentes quantidades de painéis e frequências de medição ao longo do tempo.

### Resultado do conjunto principal

```text
Medições esperadas: 288.000
Medições válidas:   283.392
Cobertura geral:     98,40%
```

A cobertura mede completude dos registros válidos e não disponibilidade física dos equipamentos.

---

# Qualidade dos dados

No conjunto sintético principal, as 4.608 medições esperadas que não resultaram em registros válidos foram decompostas em:

```text
Lacunas:     2.880
Inválidas:   1.440
Conflitos:     288
-----------------
Total:       4.608
```

---

## Lacunas

Representam medições esperadas que não chegaram ao pipeline.

---

## Registros inválidos

Representam medições recebidas, mas rejeitadas pelas regras de validação.

Distribuição no conjunto principal:

```text
Violação de domínio: 494
Valor ausente:       476
Erro de conversão:   470
------------------------
Total:             1.440
```

Campos afetados:

```text
Irradiância: 494
Temperatura: 476
Tensão:      470
```

No conjunto sintético atual, cada tipo de erro foi criado para afetar um campo específico.

Em dados reais, essa relação não precisa ser 1:1 e um único registro pode apresentar mais de um erro de validação.

---

## Conflitos

Duas versões diferentes da mesma chave natural:

```text
(timestamp, site_id, panel_id)
```

são classificadas como conflitantes.

Embora um conflito possa produzir duas linhas na quarentena, ele representa uma única medição esperada perdida quando analisado pela chave natural.

---

## Duplicatas exatas

Duplicatas exatas são descartadas durante a classificação.

Elas não reduzem a cobertura quando a medição original permanece válida.

---

# Potência e energia

A plataforma trabalha atualmente com potência em watts:

```text
power_w = voltage_v × current_a
```

Os indicadores horários e diários utilizam médias aritméticas das observações disponíveis.

A potência observada de uma instalação corresponde à soma das potências dos painéis que possuem uma medição válida naquele instante.

Portanto, lacunas podem fazer a potência observada ficar abaixo da potência efetivamente produzida pela instalação.

> O projeto ainda não calcula energia produzida em `kWh`.

Potência e energia são grandezas diferentes e não devem ser tratadas como equivalentes.

---

# Fuso horário

Os timestamps são armazenados com informação de fuso horário.

A simulação utiliza como referência local:

```text
UTC-03:00
```

Os modelos analíticos utilizam esse horário para determinar datas locais e agregações diárias.

---

# Executar o Data Warehouse

## Carregar seeds

```powershell
python scripts/run_dbt.py seed
```

## Executar modelos

```powershell
python scripts/run_dbt.py run
```

## Executar testes

```powershell
python scripts/run_dbt.py test
```

## Executar modelos e testes

```powershell
python scripts/run_dbt.py build
```

---

# Testes dbt

Última execução confirmada:

```text
PASS=106
WARN=0
ERROR=0
SKIP=0
NO-OP=0
TOTAL=106
```

A suíte inclui verificações de:

- valores obrigatórios;
- unicidade;
- regras de domínio;
- integridade entre fatos e dimensões;
- consistência das agregações;
- reconciliação entre staging e fatos;
- reconciliação das agregações horárias;
- reconciliação das agregações diárias;
- configuração da cobertura;
- períodos de configuração sobrepostos;
- limites de cobertura;
- reconciliação da cobertura com a tabela de fatos;
- decomposição da qualidade dos dados;
- reconciliação da quarentena;
- validação do detalhamento dos erros;
- reconciliação dos erros de validação.

---

# Testes Python

Com os bancos PostgreSQL iniciados:

```powershell
python -m pytest -q
```

Última execução confirmada:

```text
93 passed
```

Os testes incluem:

- validação de registros;
- duplicatas;
- conflitos;
- persistência;
- idempotência;
- transações;
- auditoria;
- rollback;
- integração com PostgreSQL;
- pipeline de ponta a ponta;
- gerador de dados sintéticos.

Os testes de banco utilizam um PostgreSQL separado do ambiente de desenvolvimento.

A suíte verifica a identidade da conexão antes de permitir a execução dos testes que alteram dados.

---

# Dashboard Power BI

O dashboard utiliza os modelos analíticos do schema `analytics` do PostgreSQL.

A conexão foi configurada utilizando o modo **Importar** do Power BI.

O PostgreSQL precisa estar disponível durante:

- importação inicial;
- atualização dos dados;
- inclusão de novas tabelas.

Após a importação, o arquivo `.pbix` pode ser utilizado para edição e exploração sem que os contêineres permaneçam em execução.

---

## Estrutura do dashboard

### 1. Visão individual

Permite selecionar:

- instalação;
- data.

Apresenta:

- potência média diária;
- pico de potência observado;
- cobertura diária;
- curva horária de potência;
- evolução da cobertura diária;
- evolução da potência média diária.

---

### 2. Comparação

Apresenta:

- instalações analisadas;
- cobertura geral;
- medições válidas;
- medições esperadas;
- potência média por instalação;
- cobertura acumulada por instalação.

---

### 3. Qualidade

Apresenta:

- medições ausentes ou rejeitadas;
- lacunas;
- medições inválidas;
- conflitos;
- perdas por instalação;
- composição das perdas;
- evolução diária das perdas de qualidade.

---

### 4. Quarentena

Apresenta:

- erros de validação por tipo;
- erros por campo afetado;
- evolução diária dos erros de validação;
- distribuição dos erros por instalação.

---

## Modelo Power BI

O modelo utiliza dimensões compartilhadas de:

- calendário;
- instalações.

Principais dimensões:

```text
Dim_Calendario
Dim_Instalacoes
```

As tabelas analíticas são relacionadas às dimensões utilizando relacionamentos:

```text
1:*
```

com direção de filtro única.

Uma tabela desconectada:

```text
Medidas
```

é utilizada exclusivamente para organização das medidas DAX.

---

# Exportação do dashboard

Uma versão exportada do dashboard em PDF está disponível em:

[Dashboard Solar Data Platform — PDF](solar_data.pdf)

O PDF apresenta as quatro páginas utilizadas no relatório Power BI:

1. Visão individual;
2. Comparação;
3. Qualidade;
4. Quarentena.

---

# Documentação adicional

- [Data Warehouse](docs/data_warehouse.md)
- [Gerador de dados sintéticos](docs/README_GENERATOR.md)
- [Dashboard Power BI — PDF](solar_data.pdf)

---

# Limitações atuais

- Os dados apresentados atualmente no dashboard são sintéticos.
- O simulador fotovoltaico é simplificado.
- O modelo não representa todas as variáveis físicas de uma instalação fotovoltaica real.
- O horário local utilizado atualmente é fixo em UTC-03:00.
- Lacunas e registros rejeitados reduzem a cobertura.
- A potência observada pode subestimar a potência total quando existem painéis sem medição válida.
- As médias atuais são aritméticas e não ponderadas pelo intervalo de tempo.
- O projeto ainda não calcula energia produzida em `kWh`.
- O conjunto sintético atual associa cada tipo de erro de validação a um campo específico por construção.
- Os indicadores de cobertura representam qualidade e completude dos dados, não disponibilidade física dos equipamentos.
- O tempo de ingestão observado foi medido em ambiente local de desenvolvimento e não deve ser interpretado como benchmark de produção.

---

# Roadmap

- Calcular energia produzida em `kWh`.
- Evoluir a modelagem temporal.
- Avaliar inserções em lote para otimizar a ingestão.
- Automatizar testes com GitHub Actions.
- Evoluir o gerenciamento de migrations.
- Adicionar orquestração do pipeline.
- Preparar publicação e documentação do dashboard para portfólio.
- Avaliar futura camada de detecção de anomalias.

---

# Segurança

Nunca faça commit de:

- `.env`;
- senhas;
- URLs contendo credenciais reais;
- tokens;
- outros segredos.

Versione somente `.env.example` com valores fictícios.