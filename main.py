"""Command-line entry point for the weather generator."""

from collections.abc import Callable

from climate_presets import climate_options
from weather_engine import ALTITUDE_LEVELS_KM, IntermittentFrontWeatherEngine
from weather_output import save_outputs


def run_simulation(
    engine: IntermittentFrontWeatherEngine,
    total_ticks: int,
    on_event: Callable[[str], None] | None = None,
) -> None:
    if total_ticks <= 0:
        raise ValueError("Tick duration must be a positive integer.")

    for tick in range(1, total_ticks + 1):
        metrics = engine.update_weather_tick(tick)
        if on_event is not None and total_ticks <= 50:
            for event in engine.events:
                on_event(event)
            on_event(metrics["report"])


def main() -> None:
    climate_codes = list(climate_options)
    while True:
        print("\n=========================================")
        print("    SPATIAL WEATHER SIMULATION ENGINE    ")
        print("=========================================")
        print("Available Codes: " + ", ".join(climate_codes[:15]))
        print("                 " + ", ".join(climate_codes[15:]))
        print("-----------------------------------------")

        user_code = input("Enter Climate Code (or type 'exit' to quit): ").strip()
        if user_code.lower() == "exit":
            print("\nShutting down simulation framework. Goodbye!")
            return

        user_season = input("Enter Season (winter, spring, summer, fall): ").strip()
        normalized_code = user_code.lower()
        climate_code = next(
            (code for code in climate_codes if code.lower() == normalized_code), None
        )
        default_altitude = (
            climate_options[climate_code].default_altitude
            if climate_code is not None
            else "sea level"
        )
        print("Altitude options (approximate elevation above sea level):")
        for level, (_, elevation_range) in ALTITUDE_LEVELS_KM.items():
            print(f"  {level}: {elevation_range}")
        user_altitude = input(
            f"Enter altitude level (blank for climate default: {default_altitude}): "
        ).strip() or None
        try:
            total_ticks = int(input("Enter simulation duration in hours (e.g., 150): "))
            if total_ticks <= 0:
                raise ValueError
        except ValueError:
            print("\n[Error] Duration must be a positive whole number of hours. Please try again.")
            continue

        try:
            engine = IntermittentFrontWeatherEngine(
                user_code, user_season, altitude=user_altitude
            )
            print(
                f"\nInitializing regions for {engine.base_data.fullname} "
                f"at {engine.altitude_level} ({engine.altitude_km:.2f} km)..."
            )
            run_simulation(engine, total_ticks, lambda event: print(f"   >> {event}"))
            if total_ticks > 50:
                print("Detailed hourly reports are included in the saved JSON log.")

            json_path, chart_path = save_outputs(engine)
            print(f" -> Log exported successfully to: {json_path}")
            print(f" -> Chart saved successfully to: {chart_path}")
        except ValueError as error:
            print(f"\n[Configuration Error] {error} Please try again.")

        print("\n-----------------------------------------")
        if input("Run another configuration? (y/n): ").strip().lower() != "y":
            print("\nShutting down simulation framework. Goodbye!")
            return


if __name__ == "__main__":
    main()
