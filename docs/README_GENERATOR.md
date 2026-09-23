# Solar Data Platform — gerador de dados sintéticos

Este pacote contém um gerador de medições fotovoltaicas **sintéticas**, testes `pytest`, um CSV de 30 dias e um manifesto JSON com parâmetros, especificação do módulo e checksum SHA-256. Coloque as pastas `scripts/`, `tests/` e `data/generated/` na raiz do seu repositório **sem substituir seus arquivos existentes**. Copie o conteúdo deste documento para o README principal quando desejar.

## Módulo de referência

Todas as instalações usam um módulo **Canadian Solar HiKu6 CS6W-550MS**, com os seguintes valores nominais de folha técnica (STC): potência máxima 550 Wp, tensão no ponto de potência máxima 41,7 V, corrente no ponto de potência máxima 13,20 A. O coeficiente térmico de potência é -0,34%/°C e o NMOT nominal é 41 ± 3 °C. Fonte do fabricante: https://www.canadiansolar.com/na/wp-content/uploads/sites/3/2026/01/CS-Datasheet-HiKu6_CS6W-MS_v2.7_EN-2278mm.pdf

A simulação é **didática e simplificada**: usa irradiância diurna senoidal, variação de nuvens por instalação, pequena dispersão entre painéis e ajuste de potência pela temperatura estimada da célula. Os valores não são medições reais, nem previsão de produção energética. `temperature_c` no CSV representa a **temperatura estimada da célula**, não temperatura ambiente. As medições são simuladas em UTC-03:00 fixo e gravadas com timestamp UTC.

## Arquivos

- `scripts/generate_solar_data.py`: gerador parametrizável, somente biblioteca padrão do Python.
- `tests/test_generate_solar_data.py`: testes unitários do gerador.
- `data/generated/solar_2026-08-01_30d_15min_10sites_10panels.csv`: dataset gerado.
- `data/generated/solar_2026-08-01_30d_15min_10sites_10panels.manifest.json`: parâmetros, distribuição das anomalias, modelo da placa e SHA-256 do CSV.

## Parâmetros CLI

```text
--start-date YYYY-MM-DD   Data inicial da simulação (padrão: 2026-08-01)
--days N                  Número de dias (padrão: 30)
--interval-minutes N      Frequência; divisor positivo de 1440 (padrão: 15)
--sites N                 Quantidade de instalações (padrão: 10)
--panels-per-site N       Painéis por instalação (padrão: 10)
--gap-pct P               Percentual de medições omitidas (padrão: 1.0)
--duplicate-pct P         Percentual de duplicatas exatas extras (padrão: 0.5)
--invalid-pct P           Percentual de medições inválidas (padrão: 0.5)
--conflict-pct P          Percentual de pares conflitantes extras (padrão: 0.0)
--seed N                  Semente para reprodução exata (padrão: 42)
--output FILE.csv         Arquivo de destino (padrão: nome calculado)
```

Todos os percentuais são calculados sobre o total **teórico** de medições, antes das lacunas; as categorias são selecionadas de modo mutuamente exclusivo. A soma dos percentuais não pode exceder 100%. A quantidade por categoria é arredondada para o inteiro mais próximo pelo gerador.

### Gerar o conjunto fornecido

Na raiz do repositório:

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
  --conflict-pct 0.1 `
  --seed 42 `
  --output data/generated/minha_nova_execucao.csv
```

O gerador **não sobrescreve** CSVs ou manifestos já existentes. Para outra configuração, use um novo nome de arquivo. Isso é especialmente importante porque o pipeline atual usa `(source_file, source_row)` para identificar a quarentena: dois arquivos de conteúdos diferentes com o mesmo nome poderiam ser confundidos ao ingerir.

### Experimentar com um conjunto pequeno primeiro

```powershell
python scripts/generate_solar_data.py --days 1 --interval-minutes 60 --sites 2 --panels-per-site 2 --gap-pct 1 --duplicate-pct 1 --invalid-pct 1 --conflict-pct 1 --output data/generated/small_test.csv
python -m pytest tests/test_generate_solar_data.py -v
```

### Ingerir o CSV no pipeline existente

`python -m src.database`, na implementação anterior, usa o arquivo raw padrão. Para ingerir o CSV sintético explicitamente, execute a partir da raiz do projeto:

```powershell
python -c "from pathlib import Path; from src.database import ingest_csv; p=Path('data/generated/solar_2026-08-01_30d_15min_10sites_10panels.csv'); result, accepted, quarantined=ingest_csv(p); print('accepted classified:',len(result['accepted']),'inserted:',accepted,'quarantined classified:',len(result['quarantined']),'quarantined inserted:',quarantined,'duplicate rows:',len(result['skipped_duplicate_rows']))"
```

**Atenção:** o CSV tem quase 287 mil linhas. A implementação atual da persistência executa um INSERT por registro e pode levar bastante tempo; teste primeiro com o conjunto pequeno. Uma otimização posterior será adotar inserção em lote/COPY e medidas de uso de memória. O `ingest_csv()` existente preserva a transação atômica de aceitos e quarentena, além de registrar a execução em `ingestion_runs`.

Após carregar, atualize o Data Warehouse:

```powershell
python scripts/run_dbt.py build
```

## Estatísticas do conjunto fornecido

| Item | Quantidade |
|---|---:|
| Dias | 30 |
| Intervalo | 15 minutos |
| Instalações | 10 |
| Painéis por instalação | 10 |
| Medições teóricas | 288.000 |
| Lacunas (1,0%) | 2.880 omitidas |
| Inválidas (0,5%) | 1.440 |
| Duplicatas extras (0,5%) | 1.440 |
| Pares conflitantes (0,1%) | 288 pares, ou 576 linhas em quarentena |
| Linhas gravadas no CSV (sem cabeçalho) | 286.848 |

Dadas as regras de classificação atuais do `process_csv()`, **esperamos** 283.392 leituras aceitas, 2.016 linhas em quarentena e 1.440 duplicatas ignoradas (total: 286.848 linhas). Essas contagens são derivadas da configuração, não constituem uma medição de desempenho do pipeline em PostgreSQL.

As lacunas são linhas omitidas. Entre as 1.440 inválidas, o gerador alterna temperatura ausente, irradiância negativa e valor não numérico de tensão. As duplicatas são cópias exatas da linha original. Os conflitos são duas versões diferentes para a mesma chave `(timestamp, site_id, panel_id)`; ambas devem ser direcionadas à quarentena. Nenhuma anomalia altera permanentemente o CSV de origem depois da geração.

### Versionamento e segurança

Recomendação: versionar `scripts/generate_solar_data.py`, `tests/test_generate_solar_data.py` e este documento. O CSV grande e os manifestos podem ser tratados como artefatos gerados fora do Git, ou controlados com Git LFS caso realmente precise deles no repositório. Preserve `.env` no `.gitignore` e não regrave um arquivo de origem que já tenha sido ingerido.
