import argparse
import csv
import re
from pathlib import Path
from typing import Dict


def read_config_csv(config_csv_path: Path) -> Dict[str, str]:
    with config_csv_path.open("r") as handle:
        reader = csv.DictReader(handle)
        row = next(reader)
        return {f"config.{key}": value for key, value in row.items()}


def parse_mcpat_metrics_with_units(file_path: Path) -> Dict[str, float]:
    with file_path.open("r") as handle:
        lines = handle.readlines()

    results: dict[str, float] = {}
    current_group = "mcpat"
    kv_pattern = re.compile(
        r"^\s*([\w\s\/\(\)-]+)\s*=\s*([0-9.eE+-]+)\s*(\w+\^?\d*|W|mm\^2)?\s*$"
    )
    for line in lines:
        line = line.strip()
        if line.endswith(":") and not line.startswith("McPAT"):
            current_group = line[:-1].strip().lower().replace(" ", "_").replace("/", "_")
            continue
        match = kv_pattern.match(line)
        if match:
            key = match.group(1).strip().lower().replace(" ", "_").replace("/", "_")
            value = float(match.group(2))
            results[f"mcpat.{current_group}.{key}"] = value
    return results


def extract_stats_metrics(stats_file: Path) -> Dict[str, float]:
    desired_keys = {
        "simSeconds",
        "simTicks",
        "finalTick",
        "simFreq",
        "hostSeconds",
        "hostTickRate",
        "hostMemory",
        "simInsts",
        "simOps",
        "hostInstRate",
        "hostOpRate",
    }
    cpu_keys = {"numCycles", "cpi", "ipc"}
    l2_pattern = re.compile(r"^system\.l2cache\.(\w+)::(\w+)\s+([0-9.eE+-]+)")
    cpu_pattern = re.compile(r"^system\.cpu\.(\w+)\s+([0-9.eE+-]+)")

    results: Dict[str, float] = {}
    with stats_file.open("r") as handle:
        for line in handle:
            tokens = line.strip().split()
            if len(tokens) >= 2 and tokens[0] in desired_keys:
                results[f"stats.{tokens[0]}"] = float(tokens[1])

            l2_match = l2_pattern.match(line.strip())
            if l2_match:
                results[
                    f"stats.l2cache.{l2_match.group(1)}.{l2_match.group(2)}"
                ] = float(l2_match.group(3))

            cpu_match = cpu_pattern.match(line.strip())
            if cpu_match and cpu_match.group(1) in cpu_keys:
                results[f"stats.cpu.{cpu_match.group(1)}"] = float(cpu_match.group(2))

    return results


def generate_csv(input_dir: Path, output_csv: Path) -> None:
    config_path = input_dir / "config.csv"
    mcpat_path = input_dir / "mcpat_results.txt"
    stats_path = input_dir / "stats.txt"

    if not config_path.exists() or not mcpat_path.exists() or not stats_path.exists():
        raise FileNotFoundError(
            "Missing one or more required files: config.csv, mcpat_results.txt, stats.txt."
        )

    config = read_config_csv(config_path)
    mcpat = parse_mcpat_metrics_with_units(mcpat_path)
    stats = extract_stats_metrics(stats_path)

    all_data = {**config, **stats, **mcpat}
    write_header = not output_csv.exists() or output_csv.stat().st_size == 0

    with output_csv.open("a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=sorted(all_data.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(all_data)

    print(f"Appended one row to {output_csv}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract config/stats/McPAT data to CSV.")
    parser.add_argument(
        "input_dir",
        type=Path,
        help="Directory containing config.csv, mcpat_results.txt, and stats.txt.",
    )
    parser.add_argument("output_csv", type=Path, help="Path to output CSV file.")
    args = parser.parse_args()
    generate_csv(args.input_dir, args.output_csv)


if __name__ == "__main__":
    main()
