"""Command-line entry point for the weather generator."""

from climate_presets import climate_options
from weather_engine import IntermittentFrontWeatherEngine
from weather_output import save_outputs
from collections.abc import Callable

def run_simulation(
    engine: IntermittentFrontWeatherEngine,
    total_ticks: int,
    on_event: Callable[[str], None] | None = None,
) -> None:
    if total_ticks <= 0:
        raise ValueError("Tick duration must be a positive integer.")

    for tick in range(1, total_ticks + 1):
        engine.update_weather_tick(tick)
        if on_event is not None:
            for event in engine.events:
                on_event(event)

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
        try:
            total_ticks = int(input("Enter timeline tracking tick duration (e.g., 150): "))
            if total_ticks <= 0:
                raise ValueError
        except ValueError:
            print("\n[Error] Tick duration must be a positive integer. Please try again.")
            continue

        try:
            engine = IntermittentFrontWeatherEngine(user_code, user_season)
            print(f"\nInitializing regions for {engine.base_data.fullname}...")
            run_simulation(engine, total_ticks, lambda event: print(f"   >> {event}"))

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
