import argparse
import re
from pathlib import Path
from typing import Dict, Tuple

import h5py


def extract_gem5_config_params(cmdline_file: Path) -> Dict[str, str]:
    params: Dict[str, str] = {}
    with cmdline_file.open("r") as handle:
        for line in handle:
            if line.startswith("command line:"):
                tokens = line.split()
                for index, token in enumerate(tokens):
                    if token.startswith("--") and "=" in token:
                        key, value = token.lstrip("--").split("=", 1)
                        if key != "outdir":
                            params[key] = value
                    elif token == "--bin" and index + 1 < len(tokens):
                        params["bin"] = tokens[index + 1]
    return params


def parse_mcpat_metrics_with_units(file_path: Path) -> Dict[str, Tuple[float, str]]:
    with file_path.open("r") as handle:
        lines = handle.readlines()

    results: Dict[str, Tuple[float, str]] = {}
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
            unit = match.group(3) or ""
            results[f"{current_group}/{key}"] = (value, unit)
    return results


def copy_stats_h5_to_output(stats_h5: Path, dst_group: h5py.Group) -> None:
    with h5py.File(stats_h5, "r") as stats_src:
        def recursive_copy(src_group: h5py.Group, dst_group: h5py.Group) -> None:
            for key in src_group:
                item = src_group[key]
                if isinstance(item, h5py.Dataset):
                    if key in dst_group:
                        del dst_group[key]
                    dst_group.create_dataset(key, data=item[()])
                    for attr_key, attr_val in item.attrs.items():
                        dst_group[key].attrs[attr_key] = attr_val
                elif isinstance(item, h5py.Group):
                    recursive_copy(item, dst_group.require_group(key))

        recursive_copy(stats_src, dst_group.create_group("stats"))


def write_all_to_hdf5(
    config: Dict[str, str],
    mcpat_data: Dict[str, Tuple[float, str]],
    stats_h5: Path,
    out_path: Path,
    group_name: str,
) -> None:
    with h5py.File(out_path, "a") as h5f:
        root_group = h5f.require_group(group_name)

        cfg_group = root_group.require_group("config")
        for key, value in config.items():
            if key in cfg_group:
                del cfg_group[key]
            cfg_group.create_dataset(key, data=value)

        for path, (value, unit) in mcpat_data.items():
            group_path, key = path.rsplit("/", 1)
            group = root_group.require_group(f"mcpat/{group_path}")
            if key in group:
                del group[key]
            dataset = group.create_dataset(key, data=value)
            if unit:
                dataset.attrs["unit"] = unit

        copy_stats_h5_to_output(stats_h5, root_group)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Combine gem5 config, McPAT output, and stats.h5 into one HDF5 summary."
    )
    parser.add_argument(
        "input_dir",
        type=Path,
        help="Directory containing cmdline.txt, mcpat_results.txt, and stats.h5.",
    )
    parser.add_argument("group_name", type=str, help="Top-level group name to write.")
    parser.add_argument("output_h5", type=Path, help="Output HDF5 path.")
    args = parser.parse_args()

    cmdline_path = args.input_dir / "cmdline.txt"
    mcpat_path = args.input_dir / "mcpat_results.txt"
    stats_path = args.input_dir / "stats.h5"
    if not cmdline_path.exists() or not mcpat_path.exists() or not stats_path.exists():
        raise FileNotFoundError(
            "Missing one or more required files: cmdline.txt, mcpat_results.txt, stats.h5."
        )

    config = extract_gem5_config_params(cmdline_path)
    mcpat = parse_mcpat_metrics_with_units(mcpat_path)
    write_all_to_hdf5(config, mcpat, stats_path, args.output_h5, args.group_name)
    print(f"Wrote group '{args.group_name}' to {args.output_h5}")


if __name__ == "__main__":
    main()
