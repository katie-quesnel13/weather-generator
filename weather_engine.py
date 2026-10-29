"""Weather simulation logic, independent of CLI and file output."""

import math
import random
from dataclasses import replace
from typing import TypedDict

from climate_presets import (
    MAX_RELATIVE_HUMIDITY_PERCENT,
    climate_options,
    get_varied_base,
)
from region_classes import ActiveFront, RegionState, WeatherState


ALTITUDE_LEVELS_KM: dict[str, tuple[float, str]] = {
    "sea level": (0.0, "0 km"),
    "low": (0.25, "0-0.5 km"),
    "low-moderate": (1.0, "0.5-1.5 km"),
    "moderate": (2.0, "1.5-2.5 km"),
    "moderate-high": (3.25, "2.5-4 km"),
    "high": (5.0, "over 4 km"),
}


class WeatherTick(TypedDict):
    tick: int
    elapsed_hours: int
    temperature_celsius: float
    relative_humidity_pct: float
    air_pressure_kpa: float
    wind_speed_kmh: float
    wind_direction: str
    precip_chance_pct: float
    precipitation_occurred: bool
    precipitation_mm: float
    front_active: bool
    report: str


class IntermittentFrontWeatherEngine:
    """Simulate weather in hourly steps around a central hub."""

    DIRECTIONS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    STANDARD_PRESSURE_KPA = 101.3
    FRONT_SPAWN_CHANCE_PERCENT = 4.0
    HOURS_PER_MONTH = 30.0 * 24.0
    FREEZING_POINT_CELSIUS = 0.0

    def __init__(
        self,
        central_climate_code: str,
        season: str,
        rng: random.Random | None = None,
        altitude: str | None = None,
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

        selected_altitude = (
            self.base_data.default_altitude if altitude is None else altitude
        )
        normalized_altitude = selected_altitude.strip().lower()
        if normalized_altitude not in ALTITUDE_LEVELS_KM:
            choices = ", ".join(ALTITUDE_LEVELS_KM)
            raise ValueError(
                f"Altitude '{selected_altitude}' is invalid. Choose from: {choices}."
            )
        self.altitude_level = normalized_altitude
        self.altitude_km = ALTITUDE_LEVELS_KM[normalized_altitude][0]
        self.reference_altitude_km = ALTITUDE_LEVELS_KM[
            self.base_data.default_altitude
        ][0]
        self.altitude_delta_km = self.altitude_km - self.reference_altitude_km
        sea_level_season = getattr(self.base_data, self.season)
        self.season_node = replace(
            sea_level_season,
            air_pressure_kpa=self._adjust_pressure_for_altitude(
                sea_level_season.air_pressure_kpa, self.altitude_delta_km
            ),
            relative_humidity_percent=self._adjust_relative_humidity_for_altitude(
                sea_level_season.relative_humidity_percent, self.altitude_delta_km
            ),
            temperature_celsius=self._adjust_temperature_for_altitude(
                sea_level_season.temperature_celsius, self.altitude_delta_km
            ),
        )
        self.standard_pressure_kpa = self._adjust_pressure_for_altitude(
            self.STANDARD_PRESSURE_KPA, self.altitude_km
        )
        self.rng = rng if rng is not None else random.Random()
        self.center = WeatherState(
            air_pressure_kpa=self.season_node.air_pressure_kpa,
            relative_humidity_percent=self.season_node.relative_humidity_percent,
            temperature_celsius=self.season_node.temperature_celsius,
        )
        self.surface_water_mm = 0.0
        self.surface_ice_mm = 0.0
        self.regions: dict[str, RegionState] = {}
        self._initialize_regions()
        self.active_front = ActiveFront()
        self.history_log: list[WeatherTick] = []
        self.events: list[str] = []

    def _adjust_pressure_for_altitude(
        self, pressure_kpa: float, altitude_delta_km: float
    ) -> float:
        return pressure_kpa * math.exp(-altitude_delta_km / 8.4)

    def _adjust_temperature_for_altitude(
        self, temperature_celsius: float, altitude_delta_km: float
    ) -> float:
        return temperature_celsius - 6.5 * altitude_delta_km

    def _adjust_relative_humidity_for_altitude(
        self, relative_humidity_percent: float, altitude_delta_km: float
    ) -> float:
        return self._clamp(
            relative_humidity_percent - 2.0 * altitude_delta_km,
            0.0,
            MAX_RELATIVE_HUMIDITY_PERCENT,
        )

    def _initialize_regions(self) -> None:
        for index, direction in enumerate(self.DIRECTIONS):
            varied = get_varied_base(self.season_node, rng=self.rng)
            self.regions[direction] = RegionState(
                air_pressure_kpa=varied["air_pressure_kpa"],
                relative_humidity_percent=varied["relative_humidity_percent"],
                temperature_celsius=varied["temperature_celsius"],
                angle_degrees=index * 45.0,
            )

    def _generate_external_front(self) -> None:
        front = self.active_front
        front.source_direction = self.rng.choice(self.DIRECTIONS)
        if self.rng.choice((True, False)):
            target_pressure = self.rng.uniform(98.5, 99.8)
            target_relative_humidity = self.rng.uniform(85.0, 100.0)
            target_temperature = self.rng.uniform(8.0, 22.0)
            front_type = "Storm System / Low Pressure Front"
        else:
            target_pressure = self.rng.uniform(103.2, 104.8)
            target_relative_humidity = self.rng.uniform(10.0, 30.0)
            target_temperature = self.rng.uniform(10.0, 30.0)
            front_type = "High-Pressure Ridge"

        front.target_pressure_kpa = round(
            self._adjust_pressure_for_altitude(target_pressure, self.altitude_km), 2
        )
        front.target_relative_humidity_percent = round(
            self._adjust_relative_humidity_for_altitude(target_relative_humidity, self.altitude_km), 1
        )
        front.target_temperature_celsius = round(
            self._adjust_temperature_for_altitude(target_temperature, self.altitude_km), 1
        )
        front.ticks_remaining = self.rng.randint(12, 24)
        self.events.append(
            f"A new {front_type} has formed to the {front.source_direction} "
            f"(Pressure: {front.target_pressure_kpa} kPa | "
            f"Relative humidity: {front.target_relative_humidity_percent}%)."
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
                region.relative_humidity_percent += (
                    front.target_relative_humidity_percent - region.relative_humidity_percent
                ) * 0.25
                previous_temperature = region.temperature_celsius
                region.temperature_celsius += (
                    front.target_temperature_celsius - region.temperature_celsius
                ) * 0.10
                region.relative_humidity_percent = (
                    self._adjust_relative_humidity_for_temperature(
                        region.relative_humidity_percent,
                        previous_temperature,
                        region.temperature_celsius,
                    )
                )
                continue

            region.air_pressure_kpa += self.rng.uniform(-0.015, 0.015)
            relative_humidity_delta = self.season_node.relative_humidity_percent - region.relative_humidity_percent
            region.relative_humidity_percent += relative_humidity_delta * 0.05 + self.rng.uniform(-1.0, 1.0)
            region.relative_humidity_percent = self._clamp(
                region.relative_humidity_percent,
                0.0,
                MAX_RELATIVE_HUMIDITY_PERCENT,
            )

    def _update_center_fluctuations(self) -> None:
        self.center.air_pressure_kpa += self.rng.uniform(-0.01, 0.01)
        previous_temperature = self.center.temperature_celsius
        self.center.temperature_celsius += self.rng.uniform(-0.15, 0.15)
        self.center.relative_humidity_percent = (
            self._adjust_relative_humidity_for_temperature(
                self.center.relative_humidity_percent,
                previous_temperature,
                self.center.temperature_celsius,
            )
        )

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

    def _advect_relative_humidity(self, wind_speed: float, wind_direction: str) -> None:
        if wind_direction == "Calm":
            delta = self.season_node.relative_humidity_percent - self.center.relative_humidity_percent
            self.center.relative_humidity_percent += delta * 0.05
        else:
            upwind_relative_humidity = self.regions[wind_direction].relative_humidity_percent
            delta = upwind_relative_humidity - self.center.relative_humidity_percent
            coefficient = min(0.35, wind_speed / 100.0)
            self.center.relative_humidity_percent += delta * coefficient

        self.center.relative_humidity_percent = self._clamp(
            self.center.relative_humidity_percent,
            0.0,
            MAX_RELATIVE_HUMIDITY_PERCENT,
        )

    @staticmethod
    def _saturation_vapor_pressure_kpa(temperature_celsius: float) -> float:
        if temperature_celsius < 0.0:
            return 0.6112 * math.exp(
                22.46 * temperature_celsius / (temperature_celsius + 272.62)
            )
        return 0.6112 * math.exp(
            17.67 * temperature_celsius / (temperature_celsius + 243.5)
        )

    def _adjust_relative_humidity_for_temperature(
        self,
        relative_humidity_percent: float,
        previous_temperature_celsius: float,
        temperature_celsius: float,
    ) -> float:
        previous_saturation = self._saturation_vapor_pressure_kpa(
            previous_temperature_celsius
        )
        current_saturation = self._saturation_vapor_pressure_kpa(temperature_celsius)
        adjusted_humidity = (
            relative_humidity_percent * previous_saturation / current_saturation
        )
        return self._clamp(
            adjusted_humidity, 0.0, MAX_RELATIVE_HUMIDITY_PERCENT
        )

    def _evaporate_surface_water(self) -> None:
        temperature = self.center.temperature_celsius
        if temperature <= self.FREEZING_POINT_CELSIUS and self.surface_water_mm > 0.0:
            self.surface_ice_mm += self.surface_water_mm
            self.surface_water_mm = 0.0
        if temperature > self.FREEZING_POINT_CELSIUS and self.surface_ice_mm > 0.0:
            melted_mm = min(self.surface_ice_mm, temperature * 0.5)
            self.surface_ice_mm -= melted_mm
            self.surface_water_mm += melted_mm

        vapor_pressure_deficit_factor = max(
            0.0, 1.0 - self.center.relative_humidity_percent / 100.0
        )
        if temperature <= self.FREEZING_POINT_CELSIUS:
            ice_temperature_factor = (
                self._saturation_vapor_pressure_kpa(temperature)
                / self._saturation_vapor_pressure_kpa(self.FREEZING_POINT_CELSIUS)
            )
            evaporated_mm = min(
                self.surface_ice_mm,
                0.2 * 0.02 * ice_temperature_factor
                * vapor_pressure_deficit_factor,
            )
            self.surface_ice_mm -= evaporated_mm
        else:
            temperature_factor = self._clamp((temperature + 5.0) / 25.0, 0.0, 1.5)
            evaporated_mm = min(
                self.surface_water_mm,
                0.2 * temperature_factor * vapor_pressure_deficit_factor,
            )
            self.surface_water_mm -= evaporated_mm

        self.center.relative_humidity_percent = self._clamp(
            self.center.relative_humidity_percent + evaporated_mm * 0.5,
            0.0,
            MAX_RELATIVE_HUMIDITY_PERCENT,
        )

    def _calculate_precipitation_chance(self) -> float:
        pressure_factor = max(
            0.0, (self.standard_pressure_kpa - self.center.air_pressure_kpa) * 12.0
        )
        relative_humidity_factor = max(0.0, (self.center.relative_humidity_percent - 45.0) * 1.8)
        chance = pressure_factor + relative_humidity_factor
        monthly_normal = self.season_node.precipitation_mm_per_month
        if monthly_normal is not None:
            chance *= self._clamp(monthly_normal / 60.0, 0.0, 2.0)
        return round(self._clamp(chance, 0.0, 100.0), 1)

    def _calculate_precipitation_amount(self, precipitation_chance: float) -> float:
        monthly_normal = self.season_node.precipitation_mm_per_month
        if monthly_normal is None:
            amount_mm = self.rng.uniform(0.1, 5.0)
        elif precipitation_chance <= 0.0:
            return 0.0
        else:
            # A 30-day month is represented by 720 hourly simulation ticks.
            amount_mm = monthly_normal / (
                self.HOURS_PER_MONTH * precipitation_chance / 100.0
            )
        return round(amount_mm, 2)

    def _record_tick(
        self, tick_id: int, wind_speed: float, wind_direction: str,
        precipitation_chance: float, precipitation_occurred: bool,
        precipitation_mm: float,
    ) -> WeatherTick:
        if self.history_log:
            previous = self.history_log[-1]
            previous_temperature = previous["temperature_celsius"]
            previous_relative_humidity = previous["relative_humidity_pct"]
            previous_pressure = previous["air_pressure_kpa"]
        else:
            previous_temperature = self.season_node.temperature_celsius
            previous_relative_humidity = self.season_node.relative_humidity_percent
            previous_pressure = self.season_node.air_pressure_kpa
        elapsed_hours = len(self.history_log) + 1
        temperature = round(self.center.temperature_celsius, 1)
        relative_humidity = round(self.center.relative_humidity_percent, 1)
        pressure = round(self.center.air_pressure_kpa, 3)
        temperature_change = temperature - previous_temperature
        relative_humidity_change = relative_humidity - previous_relative_humidity
        pressure_change = pressure - previous_pressure
        precipitation = (
            f"{precipitation_mm:.2f} mm"
            if precipitation_occurred
            else "none (0.00 mm)"
        )
        front = (
            f"active from {self.active_front.source_direction}"
            if self.active_front.source_direction is not None
            else "none"
        )
        event_summary = " | ".join(self.events) if self.events else "none"
        report = (
            f"Hour {elapsed_hours}: Temperature {temperature:.1f} °C "
            f"({temperature_change:+.1f} °C); pressure {pressure:.3f} kPa "
            f"({pressure_change:+.3f} kPa); relative humidity {relative_humidity:.1f}% "
            f"({relative_humidity_change:+.1f}%); wind from {wind_direction} "
            f"at {wind_speed:.1f} km/h; precipitation {precipitation} "
            f"(chance {precipitation_chance:.1f}%); front {front}; "
            f"events: {event_summary}."
        )
        metrics: WeatherTick = {
            "tick": tick_id,
            "elapsed_hours": elapsed_hours,
            "temperature_celsius": temperature,
            "relative_humidity_pct": relative_humidity,
            "air_pressure_kpa": pressure,
            "wind_speed_kmh": wind_speed,
            "wind_direction": wind_direction,
            "precip_chance_pct": precipitation_chance,
            "precipitation_occurred": precipitation_occurred,
            "precipitation_mm": precipitation_mm,
            "front_active": self.active_front.source_direction is not None,
            "report": report,
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
        self._advect_relative_humidity(wind_speed, wind_direction)
        self._evaporate_surface_water()
        precipitation_chance = self._calculate_precipitation_chance()
        precipitation_occurred = self.rng.random() * 100.0 < precipitation_chance
        precipitation_mm = (
            self._calculate_precipitation_amount(precipitation_chance)
            if precipitation_occurred
            else 0.0
        )
        if precipitation_occurred:
            if self.center.temperature_celsius <= self.FREEZING_POINT_CELSIUS:
                self.surface_ice_mm += precipitation_mm
            else:
                self.surface_water_mm += precipitation_mm
            self.center.relative_humidity_percent = self._clamp(
                self.center.relative_humidity_percent - precipitation_mm * 0.1,
                0.0,
                MAX_RELATIVE_HUMIDITY_PERCENT,
            )
            self.events.append(
                f"Precipitation occurred: {precipitation_mm:.2f} mm "
                f"({precipitation_chance:.1f}% chance)."
            )
        return self._record_tick(
            tick_id, wind_speed, wind_direction, precipitation_chance,
            precipitation_occurred, precipitation_mm,
        )

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))
