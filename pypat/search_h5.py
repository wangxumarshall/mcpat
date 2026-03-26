import argparse
import math
from typing import Dict

import h5py


def flatten_h5(group: h5py.Group, prefix: str = "") -> Dict[str, object]:
    result: Dict[str, object] = {}
    for key, item in group.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(item, h5py.Group):
            result.update(flatten_h5(item, path))
        elif isinstance(item, h5py.Dataset):
            try:
                value = item[()]
                if hasattr(value, "shape") and value.shape != ():
                    flattened = value.flatten()
                    result[path] = [
                        float(x) if not (isinstance(x, float) and math.isnan(x)) else "nan"
                        for x in flattened
                    ]
                else:
                    result[path] = float(value) if not math.isnan(value) else "nan"
            except Exception:
                result[path] = str(item[()])
    return result


def search(stats: Dict[str, object], term: str, search_values: bool = False) -> Dict[str, object]:
    matches: Dict[str, object] = {}
    for key, value in stats.items():
        haystack = str(value) if search_values else key
        if term.lower() in haystack.lower():
            matches[key] = value
    return matches


def main() -> None:
    parser = argparse.ArgumentParser(description="Search a gem5 HDF5 stats file.")
    parser.add_argument("stats_file", help="Path to the HDF5 stats file.")
    parser.add_argument("query", help="Key or value substring to search for.")
    parser.add_argument(
        "-v",
        "--values",
        action="store_true",
        help="Search in values instead of keys.",
    )
    args = parser.parse_args()

    with h5py.File(args.stats_file, "r") as handle:
        flat_stats = flatten_h5(handle)
        results = search(flat_stats, args.query, args.values)

    if results:
        for key, value in sorted(results.items()):
            print(f"{key}: {value}")
    else:
        print("No matches found.")


if __name__ == "__main__":
    main()
