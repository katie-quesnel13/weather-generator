"""JSON and chart output for weather simulation runs."""

from datetime import datetime
import json
from pathlib import Path

import matplotlib.pyplot as plt


def save_json(timestamp, engine, output_dir: str | Path = "generated") -> Path:
    """Write simulation metadata and tick history to a JSON file."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    filename = (
        f"weather_{engine.climate_code}_{engine.season}_"
        f"{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.json"
    )
    destination = output_path / filename
    packet = {
        "climate_code": engine.climate_code,
        "climate_fullname": engine.base_data.fullname,
        "simulated_season": engine.season,
        "total_ticks": len(engine.history_log),
        "timestamp": timestamp.isoformat(),
        "pressure_unit": "kPa",
        "timeline_data": engine.history_log,
    }
    destination.write_text(json.dumps(packet, indent=4), encoding="utf-8")
    return destination


def save_chart(timestamp, engine, output_dir: str | Path = "generated") -> Path:
    """Plot moisture, precipitation probability, and temperature history."""
    if not engine.history_log:
        raise ValueError("Cannot plot a simulation with no recorded ticks.")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    filename = (
        f"weather_{engine.climate_code}_{engine.season}_"
        f"{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.png"
    )
    destination = output_path / filename

    ticks = [item["tick"] for item in engine.history_log]
    moisture = [item["moisture_pct"] for item in engine.history_log]
    precipitation = [item["precip_chance_pct"] for item in engine.history_log]
    temperatures = [item["temperature_celsius"] for item in engine.history_log]

    figure, axis_moisture = plt.subplots(figsize=(11, 6))
    axis_moisture.set_xlabel("Simulation Timeline (Ticks)", fontsize=11, weight="bold")
    axis_moisture.set_ylabel("Percentage (%)", fontsize=11)
    lines = axis_moisture.plot(ticks, moisture, label="Hub Moisture (%)", alpha=0.8)
    lines += axis_moisture.plot(
        ticks, precipitation, linestyle="--", label="Precipitation Chance (%)", alpha=0.8
    )
    axis_moisture.set_ylim(-5, 105)
    axis_moisture.grid(True, linestyle=":", alpha=0.5)

    axis_temperature = axis_moisture.twinx()
    axis_temperature.set_ylabel("Temperature (°C)", fontsize=11)
    lines += axis_temperature.plot(
        ticks, temperatures, linestyle="-.", label="Temperature (°C)", alpha=0.8
    )
    axis_moisture.legend(lines, [line.get_label() for line in lines], loc="upper left")
    figure.suptitle(
        f"Weather Simulation Timeline Trends (Intermittent Fronts)\n"
        f"Zone: {engine.base_data.fullname} ({engine.climate_code}) | "
        f"Timeline: {len(ticks)} Ticks", fontsize=12, weight="bold"
    )
    figure.tight_layout()
    figure.savefig(destination, dpi=150)
    plt.close(figure)
    return destination


def save_outputs(engine, output_dir: str | Path = "generated") -> tuple[Path, Path]:
    """Save both JSON history and its chart; return their paths."""
    timestamp = datetime.now()
    return save_json(timestamp, engine, output_dir), save_chart(timestamp, engine, output_dir)
