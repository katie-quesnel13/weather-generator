"""Typed state objects used by the weather simulation engine."""

from dataclasses import dataclass


@dataclass
class WeatherState:
    """Weather measurements for a location."""
    air_pressure_kpa: float
    relative_humidity_percent: float
    temperature_celsius: float


@dataclass
class RegionState(WeatherState):
    """Weather state for a surrounding region, with its compass angle."""
    angle_degrees: float


@dataclass
class ActiveFront:
    """External weather system influencing one surrounding region."""
    source_direction: str | None = None
    target_pressure_kpa: float = 101.3
    target_relative_humidity_percent: float = 50.0
    target_temperature_celsius: float = 15.0
    ticks_remaining: int = 0
