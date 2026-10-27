"""Regression tests for the weather generator's core behavior."""

import random
import unittest
from unittest.mock import patch

from climate_presets import climate_options
from weather_engine import IntermittentFrontWeatherEngine
from main import run_simulation


class WeatherEngineTests(unittest.TestCase):
    def test_climate_code_is_case_insensitive(self):
        a = IntermittentFrontWeatherEngine("cfb", "winter", random.Random(4))
        b = IntermittentFrontWeatherEngine(" Cfb ", "WINTER", random.Random(4))
        self.assertEqual(a.climate_code, b.climate_code)
        self.assertEqual(a.center, b.center)

    def test_invalid_climate_and_season_raise(self):
        with self.assertRaises(ValueError):
            IntermittentFrontWeatherEngine("not-a-climate", "winter")
        with self.assertRaises(ValueError):
            IntermittentFrontWeatherEngine("Cfb", "monsoon")

    def test_preset_pressure_is_in_kpa(self):
        for climate in climate_options.values():
            for season in ("winter", "spring", "summer", "fall"):
                pressure = getattr(climate, season).air_pressure_kpa
                self.assertGreater(pressure, 90.0)
                self.assertLess(pressure, 110.0)

    def test_eight_regions_and_tick_history(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "winter", random.Random(10))
        self.assertEqual(len(engine.regions), 8)
        for tick in range(1, 21):
            engine.update_weather_tick(tick)
        self.assertEqual(len(engine.history_log), 20)
        for row in engine.history_log:
            self.assertGreaterEqual(row["moisture_pct"], 0.0)
            self.assertLessEqual(row["moisture_pct"], 100.0)
            self.assertGreaterEqual(row["precip_chance_pct"], 0.0)
            self.assertLessEqual(row["precip_chance_pct"], 100.0)
            self.assertGreater(row["air_pressure_kpa"], 90.0)
            self.assertLess(row["air_pressure_kpa"], 110.0)

    def test_seeded_runs_are_reproducible(self):
        def run():
            engine = IntermittentFrontWeatherEngine("Cfb", "winter", random.Random(123))
            for tick in range(1, 40):
                engine.update_weather_tick(tick)
            return engine.history_log
        self.assertEqual(run(), run())

    def test_precipitation_chance_can_produce_event(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "winter", random.Random(10))
        with (
            patch.object(engine, "_update_front"),
            patch.object(engine, "_update_regions"),
            patch.object(engine, "_update_center_fluctuations"),
            patch.object(engine, "_calculate_wind", return_value=(0.0, "Calm")),
            patch.object(engine, "_advect_moisture"),
            patch.object(engine, "_calculate_precipitation_chance", return_value=100.0),
            patch.object(engine.rng, "random", return_value=0.5),
        ):
            metrics = engine.update_weather_tick(1)

        self.assertTrue(metrics["precipitation_occurred"])
        self.assertTrue(any("Precipitation occurred" in event for event in engine.events))

    def test_precipitation_chance_can_produce_no_event(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "winter", random.Random(10))
        with (
            patch.object(engine, "_update_front"),
            patch.object(engine, "_update_regions"),
            patch.object(engine, "_update_center_fluctuations"),
            patch.object(engine, "_calculate_wind", return_value=(0.0, "Calm")),
            patch.object(engine, "_advect_moisture"),
            patch.object(engine, "_calculate_precipitation_chance", return_value=0.0),
            patch.object(engine.rng, "random", return_value=0.5),
        ):
            metrics = engine.update_weather_tick(1)

        self.assertFalse(metrics["precipitation_occurred"])
        self.assertFalse(any("Precipitation occurred" in event for event in engine.events))

    def test_wind_direction_matches_high_pressure_region(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "winter", random.Random(1))
        center_pressure = engine.center.air_pressure_kpa

        for direction in engine.DIRECTIONS:
            with self.subTest(direction=direction):
                for region in engine.regions.values():
                    region.air_pressure_kpa = center_pressure
                engine.regions[direction].air_pressure_kpa = center_pressure + 1.0

                wind_speed, wind_direction = engine._calculate_wind()

                self.assertGreater(wind_speed, 0.5)
                self.assertEqual(wind_direction, direction)

    def test_moisture_advection_uses_wind_from_region(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "winter", random.Random(1))
        center_pressure = engine.center.air_pressure_kpa

        for direction in engine.DIRECTIONS:
            with self.subTest(direction=direction):
                engine.center.moisture_percent = 50.0
                for region in engine.regions.values():
                    region.air_pressure_kpa = center_pressure
                    region.moisture_percent = 20.0

                engine.regions[direction].air_pressure_kpa = center_pressure + 0.1
                engine.regions[direction].moisture_percent = 80.0
                wind_speed, wind_direction = engine._calculate_wind()

                self.assertEqual(wind_direction, direction)
                engine._advect_moisture(wind_speed, wind_direction)

                self.assertAlmostEqual(engine.center.moisture_percent, 56.0)

    def test_run_simulation_records_requested_ticks(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "winter", random.Random(10))

        run_simulation(engine, 5)

        self.assertEqual(len(engine.history_log), 5)
        self.assertEqual([row["tick"] for row in engine.history_log], [1, 2, 3, 4, 5])

if __name__ == "__main__":
    unittest.main()
