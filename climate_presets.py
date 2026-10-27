from dataclasses import dataclass
import random

# Climate presets use Köppen climate codes. Pressure is in kPa, temperature in °C,
# and moisture is a percentage from 0 to 100.

@dataclass(frozen=True)
class SeasonData:
    """Baseline weather conditions for one climate and season."""
    air_pressure_kpa: float
    moisture_percent: float
    temperature_celsius: float


@dataclass(frozen=True)
class ClimateData:
    fullname: str
    winter: SeasonData
    spring: SeasonData
    summer: SeasonData
    fall: SeasonData


climate_options = {
    "Af": ClimateData(
        "Tropical Rainforest",
        winter=SeasonData(101.15, 88.0, 26.0),
        spring=SeasonData(101.1, 87.0, 27.0),
        summer=SeasonData(101.02, 90.0, 28.0),
        fall=SeasonData(101.1, 89.0, 27.0),
    ),
    "Am": ClimateData(
        "Tropical Monsoon",
        winter=SeasonData(101.3, 55.0, 24.0),  # Dry winter
        spring=SeasonData(101.05, 75.0, 29.0),
        summer=SeasonData(100.85, 92.0, 27.0),  # Intense monsoon rainfall
        fall=SeasonData(101.12, 85.0, 26.0),
    ),
    "Aw": ClimateData(
        "Tropical Wet/Dry (Savanna) - Winter Dry",
        winter=SeasonData(101.4, 45.0, 23.0),
        spring=SeasonData(101.15, 60.0, 29.0),
        summer=SeasonData(100.95, 82.0, 27.0),
        fall=SeasonData(101.2, 70.0, 25.0),
    ),
    "As": ClimateData(
        "Tropical Wet/Dry (Savanna) - Summer Dry",
        winter=SeasonData(101.05, 80.0, 26.0),
        spring=SeasonData(101.2, 65.0, 28.0),
        summer=SeasonData(101.38, 50.0, 26.0),
        fall=SeasonData(101.15, 75.0, 25.0),
    ),
    "BWh": ClimateData(
        "Hot Desert",
        winter=SeasonData(101.82, 35.0, 16.0),
        spring=SeasonData(101.45, 20.0, 28.0),
        summer=SeasonData(100.98, 12.0, 39.0),
        fall=SeasonData(101.5, 25.0, 27.0),
    ),
    "BWk": ClimateData(
        "Cold Desert",
        winter=SeasonData(102.4, 45.0, -4.0),
        spring=SeasonData(101.62, 30.0, 12.0),
        summer=SeasonData(101.05, 20.0, 26.0),
        fall=SeasonData(101.88, 35.0, 10.0),
    ),
    "BSh": ClimateData(
        "Hot Semi-Arid",
        winter=SeasonData(101.65, 45.0, 19.0),
        spring=SeasonData(101.32, 35.0, 29.0),
        summer=SeasonData(101.01, 28.0, 34.0),
        fall=SeasonData(101.4, 40.0, 25.0),
    ),
    "BSk": ClimateData(
        "Cold Semi-Arid",
        winter=SeasonData(102.2, 55.0, -1.0),
        spring=SeasonData(101.6, 42.0, 10.0),
        summer=SeasonData(101.12, 32.0, 22.0),
        fall=SeasonData(101.75, 48.0, 9.0),
    ),
    "Csa": ClimateData(
        "Hot-Summer Mediterranean",
        winter=SeasonData(101.85, 75.0, 10.0),  # Mild, wet winter
        spring=SeasonData(101.62, 60.0, 17.0),
        summer=SeasonData(101.3, 40.0, 26.0),  # Hot, dry summer
        fall=SeasonData(101.6, 62.0, 18.0),
    ),
    "Csb": ClimateData(
        "Warm-Summer Mediterranean",
        winter=SeasonData(101.9, 80.0, 9.0),
        spring=SeasonData(101.68, 65.0, 14.0),
        summer=SeasonData(101.42, 48.0, 20.0),
        fall=SeasonData(101.65, 70.0, 14.0),
    ),
    "Csc": ClimateData(
        "Cold-Summer Mediterranean",
        winter=SeasonData(101.8, 85.0, 3.0),
        spring=SeasonData(101.6, 72.0, 8.0),
        summer=SeasonData(101.45, 58.0, 13.0),
        fall=SeasonData(101.62, 78.0, 7.0),
    ),
    "Cwa": ClimateData(
        "Humid Subtropical - Winter Dry",
        winter=SeasonData(102.02, 48.0, 12.0),
        spring=SeasonData(101.4, 65.0, 22.0),
        summer=SeasonData(100.88, 84.0, 28.0),
        fall=SeasonData(101.55, 68.0, 20.0),
    ),
    "Cwb": ClimateData(
        "Subtropical Highland - Winter Dry",
        winter=SeasonData(102.1, 40.0, 9.0),
        spring=SeasonData(101.55, 55.0, 17.0),
        summer=SeasonData(101.2, 78.0, 20.0),
        fall=SeasonData(101.7, 60.0, 15.0),
    ),
    "Cwc": ClimateData(
        "Cold Subtropical Highland - Winter Dry",
        winter=SeasonData(102.05, 45.0, 3.0),
        spring=SeasonData(101.6, 58.0, 9.0),
        summer=SeasonData(101.32, 75.0, 12.0),
        fall=SeasonData(101.72, 62.0, 7.0),
    ),
    "Cfa": ClimateData(
        "Humid Subtropical",
        winter=SeasonData(101.95, 70.0, 7.0),
        spring=SeasonData(101.5, 72.0, 18.0),
        summer=SeasonData(101.1, 80.0, 27.0),
        fall=SeasonData(101.62, 75.0, 17.0),
    ),
    "Cfb": ClimateData(
        "Oceanic / Marine West Coast",
        winter=SeasonData(101.68, 84.0, 5.0),
        spring=SeasonData(101.52, 76.0, 11.0),
        summer=SeasonData(101.4, 72.0, 18.0),
        fall=SeasonData(101.55, 82.0, 11.0),
    ),
    "Cfc": ClimateData(
        "Subpolar Oceanic",
        winter=SeasonData(101.42, 88.0, 1.0),
        spring=SeasonData(101.38, 80.0, 6.0),
        summer=SeasonData(101.25, 78.0, 12.0),
        fall=SeasonData(101.35, 85.0, 6.0),
    ),
    "Dsa": ClimateData(
        "Hot-Summer Humid Continental - Dry Summer",
        winter=SeasonData(102.1, 70.0, -3.0),
        spring=SeasonData(101.55, 55.0, 12.0),
        summer=SeasonData(101.08, 35.0, 23.0),
        fall=SeasonData(101.7, 58.0, 10.0),
    ),
    "Dsb": ClimateData(
        "Warm-Summer Humid Continental - Dry Summer",
        winter=SeasonData(102.2, 75.0, -6.0),
        spring=SeasonData(101.62, 58.0, 9.0),
        summer=SeasonData(101.2, 38.0, 19.0),
        fall=SeasonData(101.8, 62.0, 7.0),
    ),
    "Dsc": ClimateData(
        "Subarctic - Dry Summer",
        winter=SeasonData(102.05, 78.0, -15.0),
        spring=SeasonData(101.6, 62.0, 3.0),
        summer=SeasonData(101.28, 44.0, 14.0),
        fall=SeasonData(101.72, 70.0, 1.0),
    ),
    "Dsd": ClimateData(
        "Extreme Subarctic - Dry Summer",
        winter=SeasonData(102.4, 72.0, -32.0),
        spring=SeasonData(101.75, 58.0, -4.0),
        summer=SeasonData(101.1, 48.0, 16.0),
        fall=SeasonData(101.85, 68.0, -10.0),
    ),
    "Dwa": ClimateData(
        "Hot-Summer Humid Continental - Dry Winter",
        winter=SeasonData(102.45, 38.0, -5.0),
        spring=SeasonData(101.48, 55.0, 13.0),
        summer=SeasonData(100.92, 80.0, 24.0),
        fall=SeasonData(101.8, 52.0, 11.0),
    ),
    "Dwb": ClimateData(
        "Warm-Summer Humid Continental - Dry Winter",
        winter=SeasonData(102.52, 40.0, -10.0),
        spring=SeasonData(101.55, 52.0, 10.0),
        summer=SeasonData(101.05, 76.0, 20.0),
        fall=SeasonData(101.92, 55.0, 7.0),
    ),
    "Dwc": ClimateData(
        "Subarctic - Dry Winter",
        winter=SeasonData(102.6, 45.0, -22.0),
        spring=SeasonData(101.68, 50.0, 2.0),
        summer=SeasonData(101.12, 72.0, 15.0),
        fall=SeasonData(102, 58.0, -2.0),
    ),
    "Dwd": ClimateData(
        "Extreme Subarctic - Dry Winter",
        winter=SeasonData(103.2, 42.0, -40.0),  # Intense Siberian/Yukon winter highs
        spring=SeasonData(101.9, 48.0, -8.0),
        summer=SeasonData(101, 68.0, 16.0),
        fall=SeasonData(102.35, 55.0, -15.0),
    ),
    "Dfa": ClimateData(
        "Hot-Summer Humid Continental",
        winter=SeasonData(101.92, 72.0, -2.0),
        spring=SeasonData(101.5, 68.0, 11.0),
        summer=SeasonData(101.15, 74.0, 23.0),
        fall=SeasonData(101.68, 71.0, 11.0),
    ),
    "Dfb": ClimateData(
        "Warm-Summer Humid Continental",
        winter=SeasonData(101.98, 75.0, -7.0),
        spring=SeasonData(101.55, 66.0, 8.0),
        summer=SeasonData(101.22, 72.0, 19.0),
        fall=SeasonData(101.75, 73.0, 8.0),
    ),
    "Dfc": ClimateData(
        "Subarctic",
        winter=SeasonData(101.9, 78.0, -18.0),
        spring=SeasonData(101.6, 68.0, 2.0),
        summer=SeasonData(101.3, 70.0, 15.0),
        fall=SeasonData(101.72, 76.0, 0.0),
    ),
    "Dfd": ClimateData(
        "Extreme Subarctic",
        winter=SeasonData(102.65, 74.0, -36.0),
        spring=SeasonData(101.8, 62.0, -6.0),
        summer=SeasonData(101.18, 66.0, 16.0),
        fall=SeasonData(102.1, 72.0, -12.0),
    ),
    "ET": ClimateData(
        "Tundra",
        winter=SeasonData(101.65, 78.0, -20.0),
        spring=SeasonData(101.5, 74.0, -7.0),
        summer=SeasonData(101.22, 80.0, 5.0),  # Short cool summer
        fall=SeasonData(101.48, 82.0, -5.0),
    ),
    "EF": ClimateData(
        "Ice Cap",
        winter=SeasonData(102.8, 20.0, -45.0),  # Cold polar high
        spring=SeasonData(102.2, 25.0, -30.0),
        summer=SeasonData(101.65, 35.0, -12.0),  # Never averages above 0
        fall=SeasonData(102.4, 28.0, -28.0),
    ),
}

def get_varied_base(
    season_node: SeasonData,
    temp_var: float = 2.5,
    press_var: float = 0.08,
    moist_var: float = 5.0,
    rng: random.Random | None = None,
) -> dict[str, float]:
    """Return randomized local conditions around a seasonal baseline.

    Pressure variation is expressed in kPa. Supply an RNG to make results
    reproducible during tests or repeatable simulations.
    """
    rng = rng if rng is not None else random.Random()
    return {
        "air_pressure_kpa": round(
            season_node.air_pressure_kpa + rng.uniform(-press_var, press_var), 3
        ),
        "moisture_percent": max(
            0.0,
            min(100.0, round(
                season_node.moisture_percent + rng.uniform(-moist_var, moist_var), 1
            )),
        ),
        "temperature_celsius": round(
            season_node.temperature_celsius + rng.uniform(-temp_var, temp_var), 1
        ),
    }