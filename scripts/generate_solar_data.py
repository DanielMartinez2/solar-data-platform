"""Generate reproducible, synthetic photovoltaic measurements for Solar Data Platform.

All measurements use a simulated Canadian Solar HiKu6 CS6W-550MS panel.
This is a simplified educational simulator, not a photovoltaic yield forecast.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, TypedDict

class ModuleSpec(TypedDict):
    manufacturer: str
    family: str
    model: str
    pmax_stc_w: float
    vmp_stc_v: float
    imp_stc_a: float
    power_temperature_coefficient_per_c: float
    nmot_c: float
    datasheet: str


class MeasurementRow(TypedDict):
    timestamp: str
    site_id: str
    panel_id: str
    irradiance_wm2: str
    temperature_c: str
    voltage_v: str
    current_a: str


MODEL: ModuleSpec = {
    "manufacturer": "Canadian Solar",
    "family": "HiKu6",
    "model": "CS6W-550MS",
    "pmax_stc_w": 550.0,
    "vmp_stc_v": 41.7,
    "imp_stc_a": 13.20,
    "power_temperature_coefficient_per_c": -0.0034,
    "nmot_c": 41.0,
    "datasheet": (
        "https://www.canadiansolar.com/na/wp-content/uploads/sites/3/2026/01/"
        "CS-Datasheet-HiKu6_CS6W-MS_v2.7_EN-2278mm.pdf"
    ),
}

FieldName = Literal[
    "timestamp",
    "site_id",
    "panel_id",
    "irradiance_wm2",
    "temperature_c",
    "voltage_v",
    "current_a",
]

FIELDS: tuple[FieldName, ...] = (
    "timestamp",
    "site_id",
    "panel_id",
    "irradiance_wm2",
    "temperature_c",
    "voltage_v",
    "current_a",
)

LOCAL_TIMEZONE = timezone(timedelta(hours=-3))


@dataclass(frozen=True)
class Config:
    start_date: date = date(2026, 8, 1)
    days: int = 30
    interval_minutes: int = 15
    sites: int = 10
    panels_per_site: int = 10
    gap_pct: float = 1.0
    duplicate_pct: float = 0.5
    invalid_pct: float = 0.5
    conflict_pct: float = 0.0
    seed: int = 42
    output: Path | None = None

    def validate(self) -> None:
        if self.days <= 0 or self.sites <= 0 or self.panels_per_site <= 0:
            raise ValueError("days, sites and panels_per_site must be positive")
        if self.interval_minutes <= 0 or 1440 % self.interval_minutes != 0:
            raise ValueError("interval_minutes must be a positive divisor of 1440")
        rates = (self.gap_pct, self.duplicate_pct, self.invalid_pct, self.conflict_pct)
        if any(not math.isfinite(rate) or rate < 0 or rate > 100 for rate in rates):
            raise ValueError("anomaly percentages must be between 0 and 100")
        if sum(rates) > 100:
            raise ValueError("sum of anomaly percentages must not exceed 100")

    @property
    def expected_rows(self) -> int:
        return (self.days * (1440 // self.interval_minutes)
                * self.sites * self.panels_per_site)

    @property
    def output_path(self) -> Path:
        if self.output is not None:
            return self.output
        rate_tag = "_".join(
            f"{label}{int(round(value * 100)):04d}"
            for label, value in (
                ("g", self.gap_pct),
                ("d", self.duplicate_pct),
                ("i", self.invalid_pct),
                ("c", self.conflict_pct),
            )
        )
        name = (
            f"solar_{self.start_date.isoformat()}_{self.days}d_"
            f"{self.interval_minutes}min_{self.sites}s_"
            f"{self.panels_per_site}p_seed{self.seed}_{rate_tag}.csv"
        )
        return Path("data/generated") / name


def plan_anomalies(config: Config, rng: random.Random) -> dict[str, set[int]]:
    """Choose disjoint source measurements for each type of anomaly."""
    total = config.expected_rows
    rates = (
        ("gap", config.gap_pct),
        ("invalid", config.invalid_pct),
        ("duplicate", config.duplicate_pct),
        ("conflict", config.conflict_pct),
    )
    counts = {
        label: math.floor(total * percent / 100 + 0.5)
        for label, percent in rates
    }
    if sum(counts.values()) > total:
        raise ValueError("rounded anomaly counts exceed the possible measurements")
    chosen = iter(rng.sample(range(total), sum(counts.values())))
    return {
        label: set(next(chosen) for _ in range(count))
        for label, count in counts.items()
    }


def build_measurement(
    instant_local: datetime,
    site_number: int,
    panel_number: int,
    *,
    cloud_factor: float,
    daily_peak: float,
    panel_factor: float,
    rng: random.Random,
) -> MeasurementRow:
    """Simplified shared site weather + small individual panel variation."""
    local_hour = (
        instant_local.hour
        + instant_local.minute / 60
        + instant_local.second / 3600
    )
    sun_angle = math.pi * (local_hour - 6.0) / 12.0
    daylight = max(0.0, math.sin(sun_angle)) ** 1.4 if 6 < local_hour < 18 else 0.0
    site_irradiance = daily_peak * daylight * cloud_factor
    irradiance = min(
        1150.0,
        max(0.0, site_irradiance * rng.uniform(0.98, 1.02)),
    )
    if irradiance < 1:
        irradiance = 0.0

    ambient_c = 19.0 + 13.0 * max(0.0, math.sin(math.pi * (local_hour - 6) / 12))
    ambient_c += rng.uniform(-0.8, 0.8) + (site_number % 4) * 0.45
    cell_temperature_c = ambient_c + (MODEL["nmot_c"] - 20.0) * irradiance / 800.0

    if irradiance == 0:
        voltage_v = 0.0
        current_a = 0.0
    else:
        temp_delta = cell_temperature_c - 25.0
        power_w = (
            MODEL["pmax_stc_w"]
            * irradiance / 1000.0
            * (1 + MODEL["power_temperature_coefficient_per_c"] * temp_delta)
            * panel_factor
        )
        power_w = max(0.0, power_w)
        # Approximate operating-point voltage: deliberately simplified.
        voltage_v = MODEL["vmp_stc_v"] * (1 - 0.0027 * temp_delta)
        voltage_v = max(1.0, voltage_v)
        current_a = power_w / voltage_v

    instant_utc = instant_local.astimezone(timezone.utc)
    return {
        "timestamp": instant_utc.isoformat(timespec="seconds"),
        "site_id": f"SITE_{site_number:03d}",
        "panel_id": f"PANEL_{panel_number:03d}",
        "irradiance_wm2": f"{irradiance:.2f}",
        "temperature_c": f"{cell_temperature_c:.2f}",
        "voltage_v": f"{voltage_v:.3f}",
        "current_a": f"{current_a:.4f}",
    }


def introduce_invalid(row: MeasurementRow, index: int) -> MeasurementRow:
    modified = row.copy()
    kind = index % 3
    if kind == 0:
        modified["temperature_c"] = ""          # missing_value
    elif kind == 1:
        modified["irradiance_wm2"] = "-45.0"  # domain_violation
    else:
        modified["voltage_v"] = "invalid"    # conversion_error
    return modified


def introduce_conflict(row: MeasurementRow) -> MeasurementRow:
    modified = row.copy()
    # Different source version for exactly the same natural key.
    modified["irradiance_wm2"] = f"{float(row['irradiance_wm2']) + 25.0:.2f}"
    return modified



def as_csv_row(row: MeasurementRow) -> dict[FieldName, str]:
    return {field: row[field] for field in FIELDS}

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate(config: Config) -> dict[str, Any]:
    config.validate()
    output = config.output_path
    manifest_path = output.with_suffix(".manifest.json")
    if output.exists() or manifest_path.exists():
        raise FileExistsError(
            f"Output already exists: {output} (or its manifest). "
            "Choose a new --output. Reusing a filename with changed data "
            "can invalidate the pipeline's current source_file/source_row key."
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(config.seed)
    anomaly_indices = plan_anomalies(config, rng)
    panel_factors = {
        (site, panel): rng.uniform(0.96, 1.02)
        for site in range(1, config.sites + 1)
        for panel in range(1, config.panels_per_site + 1)
    }
    cloud_states = {site: rng.uniform(0.75, 1.0) for site in range(1, config.sites + 1)}
    summary = {
        "expected_measurements": config.expected_rows,
        "gap_rows": 0,
        "invalid_rows": 0,
        "exact_duplicate_rows": 0,
        "conflict_extra_rows": 0,
        "written_csv_rows": 0,
    }

    start_local = datetime.combine(config.start_date, datetime.min.time(), tzinfo=LOCAL_TIMEZONE)
    slots = config.days * (1440 // config.interval_minutes)
    index = 0

    try:
        with output.open("x", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            # Shared site weather for all 10 panels at a given instant.
            for slot in range(slots):
                instant_local = start_local + timedelta(minutes=config.interval_minutes * slot)
                for site in range(1, config.sites + 1):
                    if slot % (1440 // config.interval_minutes) == 0:
                        # Day-to-day weather differences, by installation.
                        cloud_states[site] = rng.uniform(0.65, 1.0)
                    cloud_states[site] = (
                        0.90 * cloud_states[site]
                        + 0.10 * rng.uniform(0.35, 1.0)
                    )
                    cloud_factor = min(1.0, max(0.25, cloud_states[site]))
                    daily_peak = 900.0 + 100.0 * math.sin(0.4 * slot / (1440 // config.interval_minutes) + site)
                    for panel in range(1, config.panels_per_site + 1):
                        current = index
                        index += 1
                        if current in anomaly_indices["gap"]:
                            summary["gap_rows"] += 1
                            continue
                        row = build_measurement(
                            instant_local,
                            site,
                            panel,
                            cloud_factor=cloud_factor,
                            daily_peak=daily_peak,
                            panel_factor=panel_factors[(site, panel)],
                            rng=rng,
                        )
                        if current in anomaly_indices["invalid"]:
                            row = introduce_invalid(row, current)
                            summary["invalid_rows"] += 1
                        csv_row = as_csv_row(row)
                        writer.writerow(csv_row)
                        summary["written_csv_rows"] += 1
                        if current in anomaly_indices["duplicate"]:
                            writer.writerow(csv_row)  # exact string-for-string duplicate
                            summary["exact_duplicate_rows"] += 1
                            summary["written_csv_rows"] += 1
                        elif current in anomaly_indices["conflict"]:
                            writer.writerow(as_csv_row(introduce_conflict(row)))
                            summary["conflict_extra_rows"] += 1
                            summary["written_csv_rows"] += 1
        config_manifest = asdict(config)
        config_manifest["start_date"] = config.start_date.isoformat()
        config_manifest["output"] = str(output)
        manifest: dict[str, Any] = {
            "kind": "synthetic_solar_data",
            "simulator_version": 1,
            "measurement_timezone": "UTC",
            "simulation_local_timezone": "UTC-03:00 (fixed; illustrative)",
            "panel_model": MODEL,
            "config": config_manifest,
            "counts": summary,
            "csv_sha256": sha256_file(output),
            "notes": [
                "Simplified synthetic simulation, not actual production or a performance forecast.",
                "Gaps are omitted rows; invalid rows remain in CSV for quarantine.",
                "Duplicates are byte-identical data rows placed immediately after their originals.",
                "Conflicts, when enabled, have matching natural keys and distinct values.",
                "All percentages are calculated over the theoretical measurement count.",
                "Generated CSV is immutable for ingestion: use a new filename for different content.",
            ],
        }
        with manifest_path.open("x", encoding="utf-8") as file:
            json.dump(manifest, file, ensure_ascii=False, indent=2)
            file.write("\n")
    except Exception:
        # Never leave a partly generated CSV that could be ingested as valid.
        if output.exists():
            output.unlink()
        if manifest_path.exists():
            manifest_path.unlink()
        raise

    return manifest


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2026, 8, 1))
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--interval-minutes", type=int, default=15)
    parser.add_argument("--sites", type=int, default=10)
    parser.add_argument("--panels-per-site", type=int, default=10)
    parser.add_argument("--gap-pct", type=float, default=1.0)
    parser.add_argument("--duplicate-pct", type=float, default=0.5)
    parser.add_argument("--invalid-pct", type=float, default=0.5)
    parser.add_argument("--conflict-pct", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    return Config(**vars(args))


def main() -> None:
    config = parse_args()
    manifest = generate(config)
    print("CSV:", config.output_path)
    print("Manifest:", config.output_path.with_suffix(".manifest.json"))
    print("Counts:", json.dumps(manifest["counts"], indent=2))
    print("SHA-256:", manifest["csv_sha256"])


if __name__ == "__main__":
    main()
