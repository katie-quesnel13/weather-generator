# Weather Generator

A command-line weather simulator built around a central region and eight
surrounding regions. It uses Köppen climate presets and advances the weather in
hourly steps, recording conditions and exporting a JSON timeline and chart.

The presets are representative climate averages, not a local forecast. Values
are intended to be refined as my willingness to source better numbers makes possible. :p

## Requirements

- Python 3.10 or later
- Matplotlib

Install Matplotlib if it is not already available:

```powershell
python -m pip install matplotlib
```

## Run

From the project directory, start the interactive program:

```powershell
python main.py
```

The program prompts for a Köppen climate code, a season (`winter`, `spring`,
`summer`, or `fall`), an altitude level, and the simulation duration in hours.
Climate codes are case-insensitive; the available codes are shown in the CLI.
Leave the altitude prompt blank to use the selected climate's default.

For runs of up to 50 hours, hourly reports and events are printed as the
simulation runs. Longer runs are saved without printing every hourly report;
the complete timeline is still included in the JSON file.

## Altitude

Altitude options are approximate elevations above sea level. The simulator
selects a representative elevation within each range to calculate its
adjustments.

| Choice | Approximate elevation | Representative elevation |
| --- | ---: | ---: |
| `sea level` | 0 km | 0 km |
| `low` | 0-0.5 km | 0.25 km |
| `low-moderate` | 0.5-1.5 km | 1 km |
| `moderate` | 1.5-2.5 km | 2 km |
| `moderate-high` | 2.5-4 km | 3.25 km |
| `high` | over 4 km | 5 km |

Most climate presets default to `sea level`. Preset baseline conditions are treated as
representative of the climate's default altitude. Choosing another altitude applies
modifiers for the difference between the selected altitude and that reference:

- Pressure uses an exponential pressure/elevation approximation.
- Temperature changes by -6.5 C per kilometer.
- Relative humidity changes by -2 percentage points per kilometer as a simple
  dry-air approximation.

The pressure reference used to calculate precipitation probability is adjusted
from sea level to the selected altitude. The baseline adjustments apply to the
central region and all surrounding regions. Incoming fronts are adjusted from
sea level to the selected altitude.

## Precipitation and relative humidity

Seasonal climate data is stored in `climate_presets.py`. Each season includes
baseline pressure (kPa), temperature (C), relative humidity (percent), and a
monthly precipitation normal (`precipitation_mm_per_month`, in mm/month).

The precipitation normal scales the central region's precipitation
probability. When precipitation occurs, the simulation reports the amount in
millimeters per hour and records it as `precipitation_mm` in the JSON timeline.
The hourly event amount is derived from the seasonal monthly normal and
calculated probability. If a normal is left unset, the existing probability
behavior is retained and events use a generic 0.1-5.0 mm amount. A normal of
zero disables precipitation for that season.

Precipitation and evaporation affect relative humidity in the central region.
Falling precipitation reduces it slightly. Evaporation depends on temperature
and the vapor-pressure deficit: warm liquid water evaporates faster, frozen
water sublimates slowly, and evaporation stops when air is saturated or
supersaturated. Ice can melt into surface water above freezing. Temperature
changes adjust relative humidity against saturation vapor pressure, so cooling
can produce temporary supersaturation. Relative humidity is allowed up to
110% to represent that state. Surrounding regions continue to exchange
relative humidity with the center through wind and return toward their seasonal
baseline. These are simplified simulation rules rather than a full atmospheric
thermodynamics model.

## Output

Each run creates files in the `generated` directory:

- A timestamped JSON file containing climate and altitude metadata, units, and
  hourly measurements including relative humidity, precipitation probability,
  and precipitation amount.
- A PNG chart showing central relative humidity, precipitation probability,
  and temperature over time.

Pressure is measured in kPa, temperature in degrees Celsius, relative humidity
in percent, and precipitation in millimeters.
