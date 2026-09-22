import csv
from pathlib import Path

with open(
    Path(__file__).parents[1] / "data/raw/solar_readings.csv",
    encoding="utf-8",
    newline="",
) as csvfile:
    reader = csv.DictReader(csvfile)

    columns = reader.fieldnames
    if columns is None:
        raise ValueError("The CSV file has no header row.")

    different_sites = set()
    different_panels = set()
    register_counter = 0
    irradiance_wm2_type = ''
    for row in reader:
        different_sites.add(row["site_id"])
        different_panels.add(row["panel_id"])
        register_counter += 1
        if not irradiance_wm2_type:
            irradiance_wm2_type = type(row["irradiance_wm2"])
    print(f"Colunas encontradas: {columns}")
    print(f"Quantidade de colunas: {len(columns)}")
    print(f"Sites encontrados: {len(different_sites)}")
    print(f"Painéis encontrados: {len(different_panels)}")
    print(f"Total de registros: {register_counter}")
    print(f"Tipo de dado da coluna irradiance_wm2: {irradiance_wm2_type}")