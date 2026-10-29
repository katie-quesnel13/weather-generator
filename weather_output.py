"""JSON and chart output for weather simulation runs."""

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, to_hex
from matplotlib.cm import ScalarMappable


def save_json(timestamp, engine, output_dir: str | Path = "generated") -> Path:
    """Write simulation metadata and tick history to a JSON file."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    filename = (
        f"weather_{engine.climate_code}_{engine.starting_season}_"
        f"{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.json"
    )
    destination = output_path / filename
    packet = {
        "climate_code": engine.climate_code,
        "climate_fullname": engine.base_data.fullname,
        "simulated_season": engine.starting_season,
        "final_season": engine.season,
        "altitude_level": engine.altitude_level,
        "altitude_km": engine.altitude_km,
        "climate_default_altitude": engine.base_data.default_altitude,
        "climate_reference_altitude_km": engine.reference_altitude_km,
        "total_ticks": len(engine.history_log),
        "tick_duration_hours": 1,
        "total_hours": len(engine.history_log),
        "timestamp": timestamp.isoformat(),
        "pressure_unit": "kPa",
        "precipitation_unit": "mm",
        "timeline_data": engine.history_log,
    }
    destination.write_text(json.dumps(packet, indent=4), encoding="utf-8")
    return destination


@dataclass(frozen=True)
class WeatherReportBucket:
    label: str
    current: dict[str, float | str | bool]
    differences: dict[str, float]
    precipitation_total_mm: float
    precipitation_change_mm: float


def chart_bucket_hours(total_hours: int) -> int:
    """Choose a chart aggregation interval that stays readable for long runs."""
    if total_hours >= 2 * 365 * 24:
        return 30 * 24
    if total_hours >= 365 * 24:
        return 7 * 24
    if total_hours >= 30 * 24:
        return 24
    if total_hours > 7 * 24:
        return 6
    if total_hours > 2 * 24:
        return 3
    return 1


def build_weather_report_buckets(engine) -> list[WeatherReportBucket]:
    """Group hourly samples into report periods with end values and changes."""
    history = engine.history_log
    if not history:
        return []

    bucket_hours = chart_bucket_hours(len(history))
    buckets: list[WeatherReportBucket] = []
    previous: dict[str, float | str | bool] = {
        "temperature_celsius": engine.season_node.temperature_celsius,
        "relative_humidity_pct": engine.season_node.relative_humidity_percent,
        "air_pressure_kpa": engine.season_node.air_pressure_kpa,
        "wind_speed_kmh": 0.0,
        "precip_chance_pct": 0.0,
        "precipitation_mm": 0.0,
    }

    for start_index in range(0, len(history), bucket_hours):
        samples = history[start_index : start_index + bucket_hours]
        current_tick = samples[-1]
        precipitation_total = sum(sample["precipitation_mm"] for sample in samples)
        current: dict[str, float | str | bool] = {
            "temperature_celsius": current_tick["temperature_celsius"],
            "relative_humidity_pct": current_tick["relative_humidity_pct"],
            "air_pressure_kpa": current_tick["air_pressure_kpa"],
            "wind_speed_kmh": current_tick["wind_speed_kmh"],
            "wind_direction": current_tick["wind_direction"],
            "precip_chance_pct": current_tick["precip_chance_pct"],
            "front_active": current_tick["front_active"],
            "season": current_tick["season"],
        }
        comparable_fields = (
            "temperature_celsius",
            "relative_humidity_pct",
            "air_pressure_kpa",
            "wind_speed_kmh",
            "precip_chance_pct",
        )
        differences = {
            field: float(current[field]) - float(previous[field])
            for field in comparable_fields
        }
        differences["precipitation_mm"] = precipitation_total - float(
            previous["precipitation_mm"]
        )

        start_hour = start_index + 1
        end_hour = start_index + len(samples)
        if bucket_hours == 30 * 24:
            label = f"Month {(start_index // bucket_hours) + 1}"
        elif bucket_hours >= 7 * 24:
            label = f"Week {(start_index // bucket_hours) + 1}"
        elif bucket_hours >= 24:
            label = f"Day {(start_index // bucket_hours) + 1}"
        elif bucket_hours == 1:
            label = f"Hour {end_hour}"
        else:
            label = f"Hours {start_hour}-{end_hour}"

        buckets.append(
            WeatherReportBucket(
                label=label,
                current=current,
                differences=differences,
                precipitation_total_mm=precipitation_total,
                precipitation_change_mm=differences["precipitation_mm"],
            )
        )
        previous = {
            **current,
            "precipitation_mm": precipitation_total,
        }

    return buckets


def _format_value_and_change(value: float, change: float, digits: int = 1) -> str:
    return f"{value:.{digits}f} ({change:+.{digits}f})"


def _color_for_value(cmap_name: str, value: float, minimum: float, maximum: float) -> str:
    normalized = max(0.0, min(1.0, (value - minimum) / (maximum - minimum)))
    return to_hex(plt.get_cmap(cmap_name)(normalized))


def _pressure_color(pressure_kpa: float, standard_pressure_kpa: float) -> str:
    pressure_anomaly = pressure_kpa - standard_pressure_kpa
    return _color_for_value("RdYlBu_r", pressure_anomaly, -5.0, 5.0)


def _add_color_scales(figure, standard_pressure_kpa: float, figure_height: float) -> None:
    scales = [
        ("Temperature (°C)", "coolwarm", -30.0, 40.0),
        ("Relative humidity (%)", "YlGnBu", 0.0, 110.0),
        (
            f"Pressure (kPa; local standard {standard_pressure_kpa:.1f})",
            "RdYlBu_r",
            standard_pressure_kpa - 5.0,
            standard_pressure_kpa + 5.0,
        ),
        ("Wind speed (km/h)", "YlOrRd", 0.0, 120.0),
        ("Precipitation total (mm)", "Blues", 0.0, 20.0),
        ("Precipitation chance (%)", "Purples", 0.0, 100.0),
    ]
    for index, (label, cmap, minimum, maximum) in enumerate(scales):
        column = index % 3
        row = index // 3
        left = 0.04 + column * 0.32
        bottom_inches = 0.62 - row * 0.36
        colorbar_axis = figure.add_axes(
            [left, bottom_inches / figure_height, 0.28, 0.035 / figure_height]
        )
        colorbar = figure.colorbar(
            ScalarMappable(
                norm=Normalize(vmin=minimum, vmax=maximum),
                cmap=cmap,
            ),
            cax=colorbar_axis,
            orientation="horizontal",
        )
        colorbar.set_ticks(
            [minimum, (minimum + maximum) / 2, maximum]
        )
        colorbar.ax.tick_params(labelsize=7, pad=1, length=2)
        colorbar.set_label(label, fontsize=8, labelpad=1)
        colorbar.ax.xaxis.set_label_position("top")


def save_chart(timestamp, engine, output_dir: str | Path = "generated") -> Path:
    """Save a color-coded weather report table with values and period changes."""
    if not engine.history_log:
        raise ValueError("Cannot plot a simulation with no recorded ticks.")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    filename = (
        f"weather_{engine.climate_code}_{engine.starting_season}_"
        f"{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.png"
    )
    destination = output_path / filename

    buckets = build_weather_report_buckets(engine)
    headers = [
        "Period",
        "Season",
        "Temp °C\n(value / Δ)",
        "RH %\n(value / Δ)",
        "Pressure kPa\n(value / Δ)",
        "Wind km/h\n(value / Δ)",
        "Direction",
        "Precip mm\n(total / Δ)",
        "Chance %\n(value / Δ)",
        "Front",
    ]
    rows: list[list[str]] = []
    cell_colors: list[list[str]] = []
    for bucket in buckets:
        current = bucket.current
        changes = bucket.differences
        rows.append([
            bucket.label,
            str(current["season"]).title(),
            _format_value_and_change(
                float(current["temperature_celsius"]),
                changes["temperature_celsius"],
            ),
            _format_value_and_change(
                float(current["relative_humidity_pct"]),
                changes["relative_humidity_pct"],
            ),
            _format_value_and_change(
                float(current["air_pressure_kpa"]),
                changes["air_pressure_kpa"],
                2,
            ),
            _format_value_and_change(
                float(current["wind_speed_kmh"]),
                changes["wind_speed_kmh"],
            ),
            str(current["wind_direction"]),
            _format_value_and_change(
                bucket.precipitation_total_mm,
                bucket.precipitation_change_mm,
            ),
            _format_value_and_change(
                float(current["precip_chance_pct"]),
                changes["precip_chance_pct"],
            ),
            "Active" if current["front_active"] else "No",
        ])
        colors = [
            "#f1f5f9",
            "#e0f2fe",
            _color_for_value("coolwarm", float(current["temperature_celsius"]), -30, 40),
            _color_for_value("YlGnBu", float(current["relative_humidity_pct"]), 0, 110),
            _pressure_color(
                float(current["air_pressure_kpa"]),
                engine.standard_pressure_kpa,
            ),
            _color_for_value("YlOrRd", float(current["wind_speed_kmh"]), 0, 120),
            "#e2e8f0",
            _color_for_value("Blues", bucket.precipitation_total_mm, 0, 20),
            _color_for_value("Purples", float(current["precip_chance_pct"]), 0, 100),
            "#fed7aa" if current["front_active"] else "#e2e8f0",
        ]
        cell_colors.append(colors)

    total_hours = len(engine.history_log)
    bucket_hours = chart_bucket_hours(total_hours)
    if bucket_hours == 30 * 24:
        grouping = "monthly"
    elif bucket_hours >= 7 * 24:
        grouping = "weekly"
    elif bucket_hours >= 24:
        grouping = "daily"
    elif bucket_hours == 6:
        grouping = "6-hour"
    elif bucket_hours == 3:
        grouping = "3-hour"
    else:
        grouping = "hourly"

    table_height_inches = (len(rows) + 1) * 0.34
    figure_height = max(2.8, table_height_inches + 1.9)
    figure, axis = plt.subplots(figsize=(16, figure_height))
    axis.set_position([0, 0, 1, 1])
    axis.axis("off")
    table = axis.table(
        cellText=rows,
        colLabels=headers,
        cellColours=cell_colors,
        cellLoc="center",
        colLoc="center",
        loc="center",
        bbox=[
            0.01,
            0.9 / figure_height,
            0.98,
            table_height_inches / figure_height,
        ],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8.5)
    for (row_index, _), cell in table.get_celld().items():
        cell.set_edgecolor("#cbd5e1")
        cell.set_linewidth(0.5)
        if row_index == 0:
            cell.set_facecolor("#1e293b")
            cell.set_text_props(color="white", weight="bold")
        else:
            background = cell.get_facecolor()
            luminance = sum(background[:3]) / 3
            cell.set_text_props(color="white" if luminance < 0.45 else "#172033")
    figure.text(
        0.02,
        (figure_height - 0.24) / figure_height,
        f"Weather Report  |  {engine.base_data.fullname} ({engine.climate_code})",
        fontsize=15,
        weight="bold",
        color="#0f172a",
        zorder=20,
        clip_on=False,
    )
    figure.text(
        0.02,
        (figure_height - 0.52) / figure_height,
        f"{engine.starting_season.title()} start  ·  {total_hours:,} hours  ·  "
        f"{grouping} summaries  ·  Values show bucket-end reading (Δ from prior bucket)",
        fontsize=9,
        color="#475569",
        zorder=20,
        clip_on=False,
    )
    _add_color_scales(figure, engine.standard_pressure_kpa, figure_height)
    figure.savefig(destination, dpi=150)
    plt.close(figure)
    return destination


def save_outputs(engine, output_dir: str | Path = "generated") -> tuple[Path, Path]:
    """Save both JSON history and its chart; return their paths."""
    timestamp = datetime.now()
    return save_json(timestamp, engine, output_dir), save_chart(timestamp, engine, output_dir)
