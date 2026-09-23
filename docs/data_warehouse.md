
# Solar Data Platform — Data Warehouse

## Arquitetura

Os dados passam pelas seguintes camadas:

1. CSV: medições originais ou sintéticas.
2. Python: validação, normalização e classificação de anomalias.
3. PostgreSQL: medições aceitas, quarentena e auditoria.
4. dbt: staging, dimensão, fatos e indicadores analíticos.
5. Power BI: visualizações e dashboards.

## Modelos

| Modelo | Granularidade |
|---|---|
| stg_solar_readings | Uma medição válida |
| dim_panels | Um painel por instalação |
| fct_solar_readings | Uma medição válida por painel e instante |
| mart_panel_performance | Um painel por instalação |
| mart_site_performance | Uma instalação |
| mart_site_power_timeseries | Uma instalação por instante |
| mart_site_hourly_power | Uma instalação por hora |
| mart_site_daily_power | Uma instalação por dia |
| mart_site_daily_coverage | Uma instalação por dia configurado |

## Indicadores

### Potência instantânea

power_w = voltage_v × current_a

Unidade: watts (W).

### Potência observada da instalação

Soma das potências dos painéis que possuem medições
válidas em determinado instante.

Não representa necessariamente a potência de todos
os painéis instalados.

### Potência média horária e diária

Média aritmética das potências observadas nos
instantes disponíveis de cada período.

Os instantes possuem o mesmo peso, independentemente
de eventuais lacunas nas medições.

### Cobertura diária

Medições esperadas =
    quantidade de painéis × horários previstos por dia

Cobertura (%) =
    100 × medições válidas / medições esperadas

A cobertura mede a completude dos registros válidos,
não a disponibilidade física dos equipamentos.

## Configuração

O seed solar_coverage_config define, por instalação:

- Período de validade da configuração;
- Quantidade esperada de painéis;
- Intervalo entre medições, em minutos.

## Limitações atuais

- Os dados gerados são sintéticos.
- O gerador utiliza um modelo fotovoltaico simplificado.
- As datas diárias seguem o fuso fixo UTC-03:00.
- Lacunas e registros rejeitados reduzem a cobertura.
- Potências calculadas com painéis ausentes podem
  subestimar a potência total da instalação.
- As médias atuais não são ponderadas pelo tempo.
- Ainda não calculamos energia produzida em kWh.