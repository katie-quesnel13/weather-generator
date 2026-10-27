"""Weather simulation logic, independent of CLI and file output."""

import math
import random
from typing import TypedDict

from climate_presets import climate_options, get_varied_base
from region_classes import ActiveFront, RegionState, WeatherState


class WeatherTick(TypedDict):
    tick: int
    temperature_celsius: float
    moisture_pct: float
    air_pressure_kpa: float
    wind_speed_kmh: float
    wind_direction: str
    precip_chance_pct: float
    precipitation_occurred: bool
    front_active: bool


class IntermittentFrontWeatherEngine:
    """Simulate a central weather hub influenced by eight surrounding regions."""

    DIRECTIONS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    STANDARD_PRESSURE_KPA = 101.3
    FRONT_SPAWN_CHANCE_PERCENT = 4.0

    def __init__(
        self,
        central_climate_code: str,
        season: str,
        rng: random.Random | None = None,
    ) -> None:
        normalized_code = central_climate_code.strip().lower()
        self.climate_code = next(
            (code for code in climate_options if code.lower() == normalized_code), None
        )
        if self.climate_code is None:
            raise ValueError(f"Climate code '{central_climate_code}' is invalid.")

        self.season = season.strip().lower()
        self.base_data = climate_options[self.climate_code]
        if self.season not in ("winter", "spring", "summer", "fall"):
            raise ValueError(f"Season '{season}' is invalid.")

        self.season_node = getattr(self.base_data, self.season)
        self.rng = rng if rng is not None else random.Random()
        self.center = WeatherState(
            air_pressure_kpa=self.season_node.air_pressure_kpa,
            moisture_percent=self.season_node.moisture_percent,
            temperature_celsius=self.season_node.temperature_celsius,
        )
        self.regions: dict[str, RegionState] = {}
        self._initialize_regions()
        self.active_front = ActiveFront()
        self.history_log: list[WeatherTick] = []
        self.events: list[str] = []

    def _initialize_regions(self) -> None:
        for index, direction in enumerate(self.DIRECTIONS):
            varied = get_varied_base(self.season_node, rng=self.rng)
            self.regions[direction] = RegionState(
                air_pressure_kpa=varied["air_pressure_kpa"],
                moisture_percent=varied["moisture_percent"],
                temperature_celsius=varied["temperature_celsius"],
                angle_degrees=index * 45.0,
            )

    def _generate_external_front(self) -> None:
        front = self.active_front
        front.source_direction = self.rng.choice(self.DIRECTIONS)
        if self.rng.choice((True, False)):
            front.target_pressure_kpa = round(self.rng.uniform(98.5, 99.8), 2)
            front.target_moisture_percent = round(self.rng.uniform(85.0, 100.0), 1)
            front.target_temperature_celsius = round(self.rng.uniform(8.0, 22.0), 1)
            front_type = "Storm System / Low Pressure Front"
        else:
            front.target_pressure_kpa = round(self.rng.uniform(103.2, 104.8), 2)
            front.target_moisture_percent = round(self.rng.uniform(10.0, 30.0), 1)
            front.target_temperature_celsius = round(self.rng.uniform(10.0, 30.0), 1)
            front_type = "High-Pressure Ridge"

        front.ticks_remaining = self.rng.randint(12, 24)
        self.events.append(
            f"A new {front_type} has formed to the {front.source_direction} "
            f"(Pressure: {front.target_pressure_kpa} kPa | "
            f"Moisture: {front.target_moisture_percent}%)."
        )

    def _update_front(self) -> None:
        front = self.active_front
        if front.ticks_remaining > 0:
            front.ticks_remaining -= 1
            return

        if front.source_direction is not None:
            self.events.append(
                f"The front from the {front.source_direction} has completely dissipated."
            )
            front.source_direction = None

        if self.rng.uniform(0.0, 100.0) < self.FRONT_SPAWN_CHANCE_PERCENT:
            self._generate_external_front()

    def _update_regions(self) -> None:
        front = self.active_front
        for direction, region in self.regions.items():
            if front.source_direction == direction:
                region.air_pressure_kpa += (
                    front.target_pressure_kpa - region.air_pressure_kpa
                ) * 0.25
                region.moisture_percent += (
                    front.target_moisture_percent - region.moisture_percent
                ) * 0.25
                region.temperature_celsius += (
                    front.target_temperature_celsius - region.temperature_celsius
                ) * 0.10
                continue

            region.air_pressure_kpa += self.rng.uniform(-0.015, 0.015)
            moisture_delta = self.season_node.moisture_percent - region.moisture_percent
            region.moisture_percent += moisture_delta * 0.05 + self.rng.uniform(-1.0, 1.0)
            region.moisture_percent = self._clamp(region.moisture_percent, 0.0, 100.0)

    def _update_center_fluctuations(self) -> None:
        self.center.air_pressure_kpa += self.rng.uniform(-0.01, 0.01)
        self.center.temperature_celsius += self.rng.uniform(-0.15, 0.15)

    def _calculate_wind(self) -> tuple[float, str]:
        net_x = 0.0
        net_y = 0.0
        for region in self.regions.values():
            angle_radians = math.radians(region.angle_degrees)
            pressure_delta = region.air_pressure_kpa - self.center.air_pressure_kpa
            net_x += pressure_delta * math.sin(angle_radians)
            net_y += pressure_delta * math.cos(angle_radians)

        # Pressure differences are now in kPa (10x smaller than the old hPa-like
        # values), so this scale factor preserves roughly the prior wind-speed range.
        wind_speed = round(math.hypot(net_x, net_y) * 200.0, 1)
        if wind_speed <= 0.5:
            return 0.0, "Calm"

        raw_angle = math.degrees(math.atan2(net_x, net_y))
        wind_from_angle = raw_angle % 360.0
        direction_index = round(wind_from_angle / 45.0) % len(self.DIRECTIONS)
        return wind_speed, self.DIRECTIONS[direction_index]

    def _advect_moisture(self, wind_speed: float, wind_direction: str) -> None:
        if wind_direction == "Calm":
            delta = self.season_node.moisture_percent - self.center.moisture_percent
            self.center.moisture_percent += delta * 0.05
        else:
            upwind_moisture = self.regions[wind_direction].moisture_percent
            delta = upwind_moisture - self.center.moisture_percent
            coefficient = min(0.35, wind_speed / 100.0)
            self.center.moisture_percent += delta * coefficient

        self.center.moisture_percent = self._clamp(
            self.center.moisture_percent, 0.0, 100.0
        )

    def _calculate_precipitation_chance(self) -> float:
        pressure_factor = max(
            0.0, (self.STANDARD_PRESSURE_KPA - self.center.air_pressure_kpa) * 12.0
        )
        moisture_factor = max(0.0, (self.center.moisture_percent - 45.0) * 1.8)
        return round(self._clamp(pressure_factor + moisture_factor, 0.0, 100.0), 1)

    def _record_tick(
        self, tick_id: int, wind_speed: float, wind_direction: str,
        precipitation_chance: float, precipitation_occurred: bool,
    ) -> WeatherTick:
        metrics: WeatherTick = {
            "tick": tick_id,
            "temperature_celsius": round(self.center.temperature_celsius, 1),
            "moisture_pct": round(self.center.moisture_percent, 1),
            "air_pressure_kpa": round(self.center.air_pressure_kpa, 3),
            "wind_speed_kmh": wind_speed,
            "wind_direction": wind_direction,
            "precip_chance_pct": precipitation_chance,
            "precipitation_occurred": precipitation_occurred,
            "front_active": self.active_front.source_direction is not None,
        }
        self.history_log.append(metrics)
        return metrics

    def update_weather_tick(self, tick_id: int) -> WeatherTick:
        """Advance the simulation by one tick and return its recorded metrics."""
        self.events.clear()
        self._update_front()
        self._update_regions()
        self._update_center_fluctuations()
        wind_speed, wind_direction = self._calculate_wind()
        self._advect_moisture(wind_speed, wind_direction)
        precipitation_chance = self._calculate_precipitation_chance()
        precipitation_occurred = self.rng.random() * 100.0 < precipitation_chance
        if precipitation_occurred:
            self.events.append(
                f"Precipitation occurred ({precipitation_chance:.1f}% chance)."
            )
        return self._record_tick(
            tick_id, wind_speed, wind_direction, precipitation_chance,
            precipitation_occurred,
        )

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))
