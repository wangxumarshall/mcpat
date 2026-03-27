import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional

import h5py

from .profiles import normalize_gem5_config
from .templates import default_template_path


CONFIG_PATTERN = re.compile(r"config\.([a-zA-Z0-9_:\.]+)")
STAT_PATTERN = re.compile(r"stats\.([a-zA-Z0-9_\.:+\-]+)")
STAT_LINE_PATTERN = re.compile(
    r"([a-zA-Z0-9_\.:+\-]+)\s+([-+]?[0-9]+\.[0-9]+|[-+]?[0-9]+|nan|inf)"
)
IGNORE_STAT_PATTERN = re.compile(r"^---|^$")
SPECIAL_PARAM_NAMES = {
    "clock_rate_dvfs",
    "sim_second",
    "sim_ticks",
    "vdd_dvfs",
}
SAFE_EVAL_GLOBALS = {"__builtins__": {}}
SAFE_EVAL_LOCALS = {
    "float": float,
    "inf": float("inf"),
    "int": int,
    "max": max,
    "min": min,
    "nan": 0.0,
}


def parse_template(source: Path) -> ET.ElementTree:
    return ET.parse(
        source, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    )


def load_template(
    template_file: Optional[Path], template_profile: str = "x86"
) -> ET.ElementTree:
    if template_file is not None:
        return parse_template(template_file)

    candidate = default_template_path(template_profile)
    if not candidate.exists():
        raise FileNotFoundError(
            f"Default template not found at {candidate}. Pass --template explicitly."
        )
    return parse_template(candidate)


def read_config_file(config_file: Path) -> Dict[str, object]:
    with config_file.open("r") as handle:
        return json.load(handle)


def get_conf_value(conf_str: str, config: Dict[str, object]) -> object:
    parts = conf_str.split(".")
    current: object = config
    for index, key in enumerate(parts):
        if isinstance(current, list):
            if current and isinstance(current[0], dict) and key in current[0]:
                current = current[0][key]
            else:
                return 0
        elif isinstance(current, dict):
            if key not in current:
                return 0
            current = current[key]
        else:
            return 0

        if ".".join(parts[: index + 1]) == "system.cpu_clk_domain.clock":
            if isinstance(current, list) and current and isinstance(current[0], (int, float)):
                current = current[0] / 1e12
            else:
                current = 0
    return current


def read_stats_hdf5(stats_file: Path) -> Dict[int, Dict[str, str]]:
    def extract(group: h5py.Group, prefix: str = "") -> Dict[str, str]:
        result: Dict[str, str] = {}
        for key, item in group.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(item, h5py.Group):
                result.update(extract(item, path))
            elif isinstance(item, h5py.Dataset):
                try:
                    value = item[()]
                    scalar = (
                        float(value.flatten()[-1])
                        if hasattr(value, "shape") and value.shape != ()
                        else float(value)
                    )
                    result[path] = str(scalar)
                except Exception:
                    result[path] = "0.0"
        return result

    with h5py.File(stats_file, "r") as handle:
        return {0: extract(handle)}


def read_stats_txt(stats_file: Path) -> Dict[int, Dict[str, str]]:
    stats: Dict[str, str] = {}
    with stats_file.open("r") as handle:
        for line in handle:
            if not IGNORE_STAT_PATTERN.match(line):
                match = STAT_LINE_PATTERN.match(line)
                if match:
                    stat_kind = match.group(1)
                    stat_value = match.group(2)
                    stats[stat_kind] = "0.0" if stat_value == "nan" else stat_value
            if "End Simulation Statistics" in line:
                break
    return {0: stats}


def read_stats_file(stats_file: Path) -> Dict[int, Dict[str, str]]:
    if stats_file.suffix == ".h5":
        return read_stats_hdf5(stats_file)
    if stats_file.suffix == ".txt":
        return read_stats_txt(stats_file)
    raise ValueError("Unsupported stats file format. Use .txt or .h5.")


def safe_eval(expression: str) -> object:
    return eval(expression, SAFE_EVAL_GLOBALS, SAFE_EVAL_LOCALS)


def split_top_level_commas(expression: str) -> list[str]:
    parts = []
    depth = 0
    current = []

    for char in expression:
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        if char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
        current.append(char)

    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def eval_csv_expression(expression: str) -> str:
    pieces = split_top_level_commas(expression)
    return ",".join(str(safe_eval(piece)) for piece in pieces)


def substitute_config_expression(value: str, config: Dict[str, object]) -> str:
    rewritten = value
    for match in CONFIG_PATTERN.findall(value):
        rewritten = rewritten.replace(
            f"config.{match}", str(get_conf_value(match, config))
        )
    if len(split_top_level_commas(rewritten)) > 1:
        return eval_csv_expression(rewritten)
    return str(safe_eval(rewritten.replace("[", "").replace("]", "")))


def substitute_stat_expression(
    value: str, stats: Dict[int, Dict[str, str]], config: Dict[str, object]
) -> str:
    rewritten = value
    for match in STAT_PATTERN.findall(value):
        rewritten = rewritten.replace(f"stats.{match}", stats[0].get(match, "0.0"))
    try:
        if "config" in rewritten:
            rewritten = substitute_config_expression(rewritten, config)
        return str(safe_eval(rewritten))
    except ZeroDivisionError:
        return "0"


def normalize_special_tags(tree: ET.ElementTree) -> None:
    for element in tree.getroot().iter():
        if element.tag == "stat" and element.attrib.get("name") in SPECIAL_PARAM_NAMES:
            element.tag = "param"


def dump_mcpat_out(
    stats: Dict[int, Dict[str, str]],
    config: Dict[str, object],
    template_mcpat: ET.ElementTree,
    outfile: Path,
) -> None:
    root = template_mcpat.getroot()

    for param in root.iter("param"):
        value = param.attrib["value"]
        if "config" in value:
            param.attrib["value"] = substitute_config_expression(value, config)

    for stat in root.iter("stat"):
        value = stat.attrib["value"]
        if "stats" in value:
            stat.attrib["value"] = substitute_stat_expression(value, stats, config)

    normalize_special_tags(template_mcpat)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    template_mcpat.write(outfile)


def run_conversion(
    stats_file: Path,
    config_file: Path,
    outfile: Path,
    template: Optional[Path] = None,
    template_profile: str = "auto",
) -> str:
    stats = read_stats_file(stats_file)
    raw_config = read_config_file(config_file)
    config, selected_profile = normalize_gem5_config(raw_config, template_profile)
    template_tree = load_template(template, selected_profile)
    dump_mcpat_out(stats, config, template_tree, outfile)
    return selected_profile


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert gem5 stats/config into McPAT XML input."
    )
    parser.add_argument("stats_file", type=Path, help="Path to gem5 stats (.txt or .h5).")
    parser.add_argument("config_file", type=Path, help="Path to gem5 config.json.")
    parser.add_argument(
        "-t", "--template", type=Path, default=None, help="Optional McPAT template XML."
    )
    parser.add_argument(
        "--template-profile",
        type=str,
        default="auto",
        help="McPAT template profile to use when --template is omitted. "
        "Supported: auto, x86, arm64-kunpeng920.",
    )
    parser.add_argument(
        "-o",
        "--outfile",
        type=Path,
        default=Path("mcpat_input.xml"),
        help="Output McPAT XML file.",
    )
    args = parser.parse_args()
    run_conversion(
        stats_file=args.stats_file,
        config_file=args.config_file,
        outfile=args.outfile,
        template=args.template,
        template_profile=args.template_profile,
    )


if __name__ == "__main__":
    main()
