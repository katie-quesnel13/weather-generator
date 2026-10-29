"""Regression tests for the weather generator's core behavior."""

import math
import json
import random
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime
from unittest.mock import patch

from matplotlib import pyplot as plt

from climate_presets import climate_options
from climate_presets import MAX_RELATIVE_HUMIDITY_PERCENT
from weather_engine import ALTITUDE_LEVELS_KM, IntermittentFrontWeatherEngine
from main import parse_duration_hours, run_simulation
from weather_output import (
    _add_color_scales,
    _pressure_color,
    build_weather_report_buckets,
    chart_bucket_hours,
    decode_timeline,
    save_chart,
    save_json,
)


class WeatherEngineTests(unittest.TestCase):
    def test_duration_parser_defaults_to_hours_and_converts_units(self):
        examples = {
            "24": 24,
            "24 hours": 24,
            "2 days": 48,
            "3 weeks": 3 * 7 * 24,
            "1 month": 30 * 24,
            "2 years": 2 * 365 * 24,
            "2 weeks 3 days": (2 * 7 + 3) * 24,
            "1 year 2 months 5 days 4 hours": (365 + 2 * 30 + 5) * 24 + 4,
            "0 weeks 3 days": 3 * 24,
            " 1 DAY ": 24,
        }
        for duration, expected_hours in examples.items():
            with self.subTest(duration=duration):
                self.assertEqual(parse_duration_hours(duration), expected_hours)

    def test_duration_parser_rejects_invalid_entries(self):
        for duration in (
            "", "0", "-1 days", "1.5 weeks", "2 fortnights", "days",
            "2 weeks, 3 days", "2 weeks 3", "2 weeks and 3 days",
        ):
            with self.subTest(duration=duration):
                with self.assertRaises(ValueError):
                    parse_duration_hours(duration)

    def test_climate_code_is_case_insensitive(self):
        a = IntermittentFrontWeatherEngine("cfb", "winter", random.Random(4))
        b = IntermittentFrontWeatherEngine(" Cfb ", "WINTER", random.Random(4))
        self.assertEqual(a.climate_code, b.climate_code)
        self.assertEqual(a.center, b.center)

    def test_season_lengths_align_to_a_365_day_year(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "winter", random.Random(4))

        winter_hours = engine.SEASON_LENGTH_DAYS["winter"] * 24
        engine.season_elapsed_hours = winter_hours - 1
        engine._advance_season()
        self.assertEqual(engine.season, "winter")
        self.assertFalse(engine.events)

        engine.season_elapsed_hours += 1
        engine._advance_season()
        self.assertEqual(engine.season, "spring")
        self.assertEqual(engine.season_node, climate_options["Cfb"].spring)
        self.assertTrue(any("day 1 of its 92-day period" in event for event in engine.events))

        engine.events.clear()
        engine.season_elapsed_hours = engine.SEASON_LENGTH_DAYS["spring"] * 24
        engine._advance_season()
        self.assertEqual(engine.season, "summer")
        engine.season_elapsed_hours = engine.SEASON_LENGTH_DAYS["summer"] * 24
        engine._advance_season()
        self.assertEqual(engine.season, "fall")
        engine.season_elapsed_hours = engine.SEASON_LENGTH_DAYS["fall"] * 24
        engine._advance_season()
        self.assertEqual(engine.season, "winter")
        self.assertEqual(sum(engine.SEASON_LENGTH_DAYS.values()), 365)

    def test_invalid_climate_and_season_raise(self):
        with self.assertRaises(ValueError):
            IntermittentFrontWeatherEngine("not-a-climate", "winter")
        with self.assertRaises(ValueError):
            IntermittentFrontWeatherEngine("Cfb", "monsoon")
        with self.assertRaises(ValueError):
            IntermittentFrontWeatherEngine("Cfb", "winter", altitude="mountain")

    def test_altitude_modifies_center_and_all_region_baselines(self):
        sea_level = IntermittentFrontWeatherEngine(
            "Cfb", "summer", random.Random(4), altitude="sea level"
        )
        high_altitude = IntermittentFrontWeatherEngine(
            "Cfb", "summer", random.Random(4), altitude="high"
        )

        self.assertAlmostEqual(
            high_altitude.center.air_pressure_kpa,
            sea_level.center.air_pressure_kpa * math.exp(-5.0 / 8.4),
        )
        self.assertAlmostEqual(
            high_altitude.center.temperature_celsius,
            sea_level.center.temperature_celsius - 6.5 * 5.0,
        )
        self.assertAlmostEqual(
            high_altitude.center.relative_humidity_percent,
            sea_level.center.relative_humidity_percent - 2.0 * 5.0,
        )
        for direction in sea_level.DIRECTIONS:
            self.assertLess(
                high_altitude.regions[direction].air_pressure_kpa,
                sea_level.regions[direction].air_pressure_kpa,
            )
            self.assertLess(
                high_altitude.regions[direction].temperature_celsius,
                sea_level.regions[direction].temperature_celsius,
            )
            self.assertLess(
                high_altitude.regions[direction].relative_humidity_percent,
                sea_level.regions[direction].relative_humidity_percent,
            )

    def test_sea_level_keeps_preset_baselines(self):
        engine = IntermittentFrontWeatherEngine(
            "Cfb", "summer", random.Random(4), altitude="sea level"
        )
        season = climate_options["Cfb"].summer

        self.assertEqual(engine.center.air_pressure_kpa, season.air_pressure_kpa)
        self.assertEqual(engine.center.temperature_celsius, season.temperature_celsius)
        self.assertEqual(engine.center.relative_humidity_percent, season.relative_humidity_percent)
        self.assertEqual(engine.standard_pressure_kpa, engine.STANDARD_PRESSURE_KPA)

    def test_highland_climates_default_to_moderate_altitude(self):
        for climate_code in ("Cwb", "Cwc"):
            with self.subTest(climate=climate_code):
                engine = IntermittentFrontWeatherEngine(
                    climate_code, "summer", random.Random(4)
                )
                self.assertEqual(engine.altitude_level, "moderate")
                self.assertEqual(engine.altitude_km, 2.0)
                self.assertEqual(engine.reference_altitude_km, 2.0)
                season = climate_options[climate_code].summer
                self.assertEqual(engine.center.air_pressure_kpa, season.air_pressure_kpa)
                self.assertEqual(engine.center.temperature_celsius, season.temperature_celsius)
                self.assertEqual(engine.center.relative_humidity_percent, season.relative_humidity_percent)

    def test_explicit_altitude_overrides_climate_default(self):
        engine = IntermittentFrontWeatherEngine(
            "Cwb", "summer", random.Random(4), altitude="high"
        )

        self.assertEqual(engine.altitude_level, "high")
        self.assertEqual(engine.altitude_km, 5.0)
        self.assertEqual(engine.reference_altitude_km, 2.0)
        self.assertAlmostEqual(
            engine.center.temperature_celsius,
            climate_options["Cwb"].summer.temperature_celsius - 6.5 * 3.0,
        )

    def test_altitude_choices_include_context_ranges(self):
        self.assertEqual(ALTITUDE_LEVELS_KM["sea level"], (0.0, "0 km"))
        self.assertEqual(ALTITUDE_LEVELS_KM["high"], (5.0, "over 4 km"))

    def test_preset_pressure_is_in_kpa(self):
        for climate in climate_options.values():
            for season in ("winter", "spring", "summer", "fall"):
                pressure = getattr(climate, season).air_pressure_kpa
                self.assertGreater(pressure, 70.0)
                self.assertLess(pressure, 110.0)

    def test_eight_regions_and_tick_history(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "winter", random.Random(10))
        self.assertEqual(len(engine.regions), 8)
        for tick in range(1, 21):
            engine.update_weather_tick(tick)
        self.assertEqual(len(engine.history_log), 20)
        for row in engine.history_log:
            self.assertGreaterEqual(row["relative_humidity_pct"], 0.0)
            self.assertLessEqual(row["relative_humidity_pct"], MAX_RELATIVE_HUMIDITY_PERCENT)
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
            patch.object(engine, "_advect_relative_humidity"),
            patch.object(engine, "_calculate_precipitation_chance", return_value=100.0),
            patch.object(engine.rng, "random", return_value=0.5),
        ):
            metrics = engine.update_weather_tick(1)

        self.assertTrue(metrics["precipitation_occurred"])
        self.assertGreater(metrics["precipitation_mm"], 0.0)
        self.assertGreater(engine.surface_water_mm, 0.0)
        self.assertLess(engine.center.relative_humidity_percent, engine.season_node.relative_humidity_percent)
        self.assertIn("mm", metrics["report"])
        self.assertTrue(any("Precipitation occurred" in event for event in engine.events))

    def test_precipitation_chance_can_produce_no_event(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "winter", random.Random(10))
        with (
            patch.object(engine, "_update_front"),
            patch.object(engine, "_update_regions"),
            patch.object(engine, "_update_center_fluctuations"),
            patch.object(engine, "_calculate_wind", return_value=(0.0, "Calm")),
            patch.object(engine, "_advect_relative_humidity"),
            patch.object(engine, "_calculate_precipitation_chance", return_value=0.0),
            patch.object(engine.rng, "random", return_value=0.5),
        ):
            metrics = engine.update_weather_tick(1)

        self.assertFalse(metrics["precipitation_occurred"])
        self.assertEqual(metrics["precipitation_mm"], 0.0)
        self.assertFalse(any("Precipitation occurred" in event for event in engine.events))

    def test_precipitation_normal_scales_chance_and_event_amount(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "winter", random.Random(10))
        engine.season_node = replace(
            engine.season_node,
            precipitation_mm_per_month=120.0,
        )
        engine.center.air_pressure_kpa = 100.0
        engine.center.relative_humidity_percent = 80.0

        chance = engine._calculate_precipitation_chance()
        amount = engine._calculate_precipitation_amount(chance)

        self.assertEqual(chance, 100.0)
        self.assertAlmostEqual(amount, 120.0 / 720.0, places=2)

    def test_zero_precipitation_normal_prevents_precipitation(self):
        engine = IntermittentFrontWeatherEngine("BWh", "summer", random.Random(10))
        engine.season_node = replace(
            engine.season_node,
            precipitation_mm_per_month=0.0,
        )
        engine.center.air_pressure_kpa = 99.0
        engine.center.relative_humidity_percent = 100.0

        self.assertEqual(engine._calculate_precipitation_chance(), 0.0)

    def test_rain_reduces_relative_humidity_and_evaporates_in_following_hours(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "summer", random.Random(10))
        engine.center.relative_humidity_percent = 50.0
        engine.center.temperature_celsius = 20.0
        engine.surface_water_mm = 5.0

        engine._evaporate_surface_water()

        self.assertLess(engine.surface_water_mm, 5.0)
        self.assertGreater(engine.center.relative_humidity_percent, 50.0)

    def test_frozen_water_evaporates_more_slowly_than_liquid_water(self):
        liquid = IntermittentFrontWeatherEngine("Cfb", "summer", random.Random(10))
        frozen = IntermittentFrontWeatherEngine("Cfb", "winter", random.Random(10))
        liquid.center.relative_humidity_percent = 50.0
        liquid.surface_water_mm = 5.0
        frozen.center.relative_humidity_percent = 50.0
        frozen.surface_ice_mm = 5.0
        liquid.center.temperature_celsius = 20.0
        frozen.center.temperature_celsius = -10.0

        liquid._evaporate_surface_water()
        frozen._evaporate_surface_water()

        self.assertGreater(
            5.0 - liquid.surface_water_mm,
            5.0 - frozen.surface_ice_mm,
        )

    def test_surface_water_freezes_when_temperature_drops_below_freezing(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "fall", random.Random(10))
        engine.center.temperature_celsius = -1.0
        engine.surface_water_mm = 2.0

        engine._evaporate_surface_water()

        self.assertEqual(engine.surface_water_mm, 0.0)
        self.assertAlmostEqual(engine.surface_ice_mm, 2.0, places=2)

    def test_saturated_air_restricts_evaporation_and_supersaturation_is_allowed(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "summer", random.Random(10))
        engine.center.temperature_celsius = 20.0
        engine.surface_water_mm = 5.0
        engine.center.relative_humidity_percent = 105.0

        engine._evaporate_surface_water()

        self.assertEqual(engine.surface_water_mm, 5.0)
        self.assertEqual(engine.center.relative_humidity_percent, 105.0)

    def test_cooling_can_raise_relative_humidity_above_saturation(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "summer", random.Random(10))
        engine.center.temperature_celsius = 20.0
        engine.center.relative_humidity_percent = 99.99
        engine.rng = random.Random(2)
        engine.rng.uniform = lambda minimum, maximum: -0.15

        engine._update_center_fluctuations()

        self.assertGreater(engine.center.relative_humidity_percent, 100.0)
        self.assertLessEqual(
            engine.center.relative_humidity_percent,
            MAX_RELATIVE_HUMIDITY_PERCENT,
        )

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

    def test_simulated_wind_speeds_stay_in_a_reasonable_range(self):
        engine = IntermittentFrontWeatherEngine("Cwb", "summer", random.Random(123))
        speeds = [
            engine.update_weather_tick(tick)["wind_speed_kmh"]
            for tick in range(1, 1001)
        ]
        ordered_speeds = sorted(speeds)

        self.assertLess(ordered_speeds[len(ordered_speeds) // 2], 30.0)
        self.assertLess(ordered_speeds[int(len(ordered_speeds) * 0.9)], 50.0)
        self.assertLess(max(ordered_speeds), 70.0)

    def test_relative_humidity_advection_uses_wind_from_region(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "winter", random.Random(1))
        center_pressure = engine.center.air_pressure_kpa

        for direction in engine.DIRECTIONS:
            with self.subTest(direction=direction):
                engine.center.relative_humidity_percent = 50.0
                for region in engine.regions.values():
                    region.air_pressure_kpa = center_pressure
                    region.relative_humidity_percent = 20.0

                engine.regions[direction].air_pressure_kpa = center_pressure + 1.0
                engine.regions[direction].relative_humidity_percent = 80.0
                wind_speed, wind_direction = engine._calculate_wind()

                self.assertEqual(wind_direction, direction)
                engine._advect_relative_humidity(wind_speed, wind_direction)

                self.assertAlmostEqual(engine.center.relative_humidity_percent, 51.5)

    def test_run_simulation_records_requested_ticks(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "winter", random.Random(10))

        run_simulation(engine, 5)

        self.assertEqual(len(engine.history_log), 5)
        self.assertEqual([row["tick"] for row in engine.history_log], [1, 2, 3, 4, 5])
        self.assertEqual([row["elapsed_hours"] for row in engine.history_log], [1, 2, 3, 4, 5])
        self.assertIn("Hour 1:", engine.history_log[0]["report"])
        self.assertIn("wind from", engine.history_log[0]["report"])
        self.assertIn("relative humidity", engine.history_log[0]["report"])
        self.assertIn("precipitation", engine.history_log[0]["report"])

    def test_run_simulation_prints_reports_only_for_at_most_50_ticks(self):
        short_engine = IntermittentFrontWeatherEngine("Cfb", "winter", random.Random(10))
        short_console: list[str] = []
        run_simulation(short_engine, 50, short_console.append)
        self.assertTrue(any(message.startswith("Hour 1:") for message in short_console))

        long_engine = IntermittentFrontWeatherEngine("Cfb", "winter", random.Random(10))
        long_console: list[str] = []
        run_simulation(long_engine, 51, long_console.append)
        self.assertEqual(long_console, [])
        self.assertTrue(all("report" in row for row in long_engine.history_log))

    def test_chart_aggregation_scales_with_simulation_duration(self):
        self.assertEqual(chart_bucket_hours(48), 1)
        self.assertEqual(chart_bucket_hours(49), 3)
        self.assertEqual(chart_bucket_hours(168), 3)
        self.assertEqual(chart_bucket_hours(169), 6)
        self.assertEqual(chart_bucket_hours(30 * 24), 24)
        self.assertEqual(chart_bucket_hours(365 * 24), 168)
        self.assertEqual(chart_bucket_hours(2 * 365 * 24), 30 * 24)

    def test_weather_report_buckets_show_end_values_changes_and_precipitation_total(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "summer", random.Random(10))
        engine.history_log = [
            {
                "elapsed_hours": hour,
                "temperature_celsius": 10.0 + hour,
                "relative_humidity_pct": 60.0 + hour,
                "air_pressure_kpa": 101.0,
                "wind_speed_kmh": float(hour),
                "wind_direction": "W",
                "precip_chance_pct": 20.0,
                "precipitation_mm": 0.5,
                "front_active": False,
                "season": "summer",
            }
            for hour in range(1, 51)
        ]

        buckets = build_weather_report_buckets(engine)

        self.assertEqual(len(buckets), 17)
        self.assertEqual(buckets[0].label, "Hours 1-3")
        self.assertEqual(buckets[0].current["temperature_celsius"], 13.0)
        self.assertAlmostEqual(
            buckets[0].differences["temperature_celsius"],
            13.0 - engine.season_node.temperature_celsius,
        )
        self.assertEqual(buckets[0].precipitation_total_mm, 1.5)
        self.assertEqual(buckets[0].precipitation_change_mm, 1.5)

    def test_weather_report_chart_is_saved(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "summer", random.Random(10))
        engine.starting_season = "winter"
        engine.season = "spring"
        engine.update_weather_tick(1)

        with tempfile.TemporaryDirectory() as output_dir:
            chart_path = save_chart(datetime.now(), engine, output_dir)

            self.assertTrue(chart_path.is_file())
            self.assertGreater(chart_path.stat().st_size, 0)
            self.assertIn("_winter_", chart_path.name)

    def test_multi_year_chart_uses_month_labels(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "summer", random.Random(10))
        engine.history_log = [
            {
                "elapsed_hours": hour,
                "temperature_celsius": 10.0,
                "relative_humidity_pct": 60.0,
                "air_pressure_kpa": 101.0,
                "wind_speed_kmh": 5.0,
                "wind_direction": "W",
                "precip_chance_pct": 20.0,
                "precipitation_mm": 0.1,
                "front_active": False,
                "season": "summer",
            }
            for hour in range(1, 2 * 365 * 24 + 1)
        ]

        buckets = build_weather_report_buckets(engine)

        self.assertEqual(len(buckets), 25)
        self.assertEqual(buckets[0].label, "Month 1")
        self.assertEqual(buckets[-1].label, "Month 25")
        self.assertAlmostEqual(buckets[0].precipitation_total_mm, 72.0)

    def test_json_filename_uses_starting_season(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "summer", random.Random(10))
        engine.starting_season = "winter"
        engine.season = "spring"

        with tempfile.TemporaryDirectory() as output_dir:
            json_path = save_json(datetime.now(), engine, output_dir)

            self.assertIn("_winter_", json_path.name)

    def test_json_stores_compact_timeline_with_implicit_elapsed_hours(self):
        engine = IntermittentFrontWeatherEngine("Cfb", "summer", random.Random(10))
        for tick in range(1, 4):
            engine.update_weather_tick(tick)

        with tempfile.TemporaryDirectory() as output_dir:
            json_path = save_json(datetime.now(), engine, output_dir)
            serialized_packet = json_path.read_text(encoding="utf-8")
            packet = json.loads(serialized_packet)

        self.assertEqual(packet["format_version"], 2)
        self.assertNotIn("total_ticks", packet)
        self.assertNotIn("total_hours", packet)
        self.assertNotIn("tick", packet["timeline_fields"])
        self.assertNotIn("elapsed_hours", packet["timeline_fields"])
        self.assertEqual(len(packet["timeline_data"]), 3)
        timeline_text = serialized_packet.split('"timeline_data": [\n', 1)[1].split(
            "\n  ]", 1
        )[0]
        timeline_lines = timeline_text.splitlines()
        self.assertEqual(len(timeline_lines), 3)
        self.assertTrue(all(line.startswith("    [") for line in timeline_lines))
        self.assertTrue(all(line.endswith("],") for line in timeline_lines[:-1]))
        self.assertTrue(timeline_lines[-1].endswith("]"))
        self.assertTrue(all(len(row) == len(packet["timeline_fields"]) for row in packet["timeline_data"]))
        decoded = decode_timeline(packet)
        for source, row in zip(engine.history_log, decoded):
            self.assertEqual(
                row,
                source,
            )

    def test_pressure_colors_track_anomaly_around_local_standard(self):
        standard = 90.0
        low_color = _pressure_color(standard - 4.0, standard)
        normal_color = _pressure_color(standard, standard)
        high_color = _pressure_color(standard + 4.0, standard)

        self.assertNotEqual(low_color, normal_color)
        self.assertNotEqual(normal_color, high_color)
        self.assertNotEqual(low_color, high_color)

    def test_chart_includes_labeled_scales_for_colored_parameters(self):
        figure = plt.figure()
        try:
            _add_color_scales(figure, 101.3, 3.0)
            labels = {
                axis.get_xlabel()
                for axis in figure.axes
                if axis.get_xlabel()
            }

            self.assertEqual(len(labels), 6)
            self.assertTrue(any(label.startswith("Temperature (°C)") for label in labels))
            self.assertTrue(any(label.startswith("Relative humidity (%)") for label in labels))
            self.assertTrue(any(label.startswith("Pressure (kPa; local standard") for label in labels))
            self.assertTrue(any(label.startswith("Wind speed (km/h)") for label in labels))
            self.assertTrue(any(label.startswith("Precipitation total (mm)") for label in labels))
            self.assertTrue(any(label.startswith("Precipitation chance (%)") for label in labels))
        finally:
            plt.close(figure)

if __name__ == "__main__":
    unittest.main()
