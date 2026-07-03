"""
DroneSync CLI — run individual pipeline modules or the full demo.
Usage: python cli.py [command]
"""
import argparse
import sys


def cmd_demo(_args):
    from main import run_demo
    run_demo()


def cmd_mission(_args):
    from main import run_single_drone
    run_single_drone()


def cmd_swarm(_args):
    from main import run_swarm
    run_swarm()


def cmd_security(_args):
    from main import run_security, run_threat_defense
    run_threat_defense()
    run_security()


def cmd_weather(args):
    from miner.weather import WeatherService, WeatherImpactAnalyzer
    from miner.planner import DronePlanner
    from main import FakeMission
    service = WeatherService(lat=args.lat, lon=args.lon)
    weather = service.get_current()
    mission = FakeMission()
    planner = DronePlanner()
    traj = planner.plan_trajectory(mission)
    analyzer = WeatherImpactAnalyzer()
    impact = analyzer.analyze(weather, traj.positions)
    for k, v in impact.items():
        print(f"{k}: {v}")


def cmd_energy(_args):
    from main import run_energy
    run_energy()


def cmd_citymap(args):
    from miner.citymap import CityMap
    city = CityMap(city=args.city)
    stats = city.get_city_stats()
    print(f"city: {stats['city']}")
    print(f"no-fly zones: {stats['no_fly_zones']}")
    print(f"zone types: {stats['zone_types']}")


def cmd_test(_args):
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v"],
        cwd="."
    )
    sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(
        description="DroneSync Subnet CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
commands:
  demo       Run full pipeline demo
  mission    Run single drone mission
  swarm      Run 3-drone swarm mission
  security   Run threat defense + security checks
  weather    Show current weather impact
  energy     Run energy optimizer
  citymap    Show city no-fly zones
  test       Run test suite
        """
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("demo", help="Full pipeline demo")
    sub.add_parser("mission", help="Single drone mission")
    sub.add_parser("swarm", help="3-drone swarm")
    sub.add_parser("security", help="Security + threat defense")

    w = sub.add_parser("weather", help="Weather impact analysis")
    w.add_argument("--lat", type=float, default=None, help="Latitude")
    w.add_argument("--lon", type=float, default=None, help="Longitude")

    sub.add_parser("energy", help="Energy optimizer")

    cm = sub.add_parser("citymap", help="City no-fly zones")
    cm.add_argument("--city", default=None, choices=["zurich", "berlin", "kyiv"])

    sub.add_parser("test", help="Run test suite")

    args = parser.parse_args()

    dispatch = {
        "demo": cmd_demo,
        "mission": cmd_mission,
        "swarm": cmd_swarm,
        "security": cmd_security,
        "weather": cmd_weather,
        "energy": cmd_energy,
        "citymap": cmd_citymap,
        "test": cmd_test,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
