from __future__ import annotations

import re
from pathlib import Path
from typing import Dict


_POWER_PATTERN = re.compile(
    r"^\s*(Total Leakage|Subthreshold Leakage|Gate Leakage|Runtime Dynamic|Peak Dynamic)\s*=\s*([0-9eE+\-.]+)\s*W"
)


def _parse_verbose_summary(result_file: Path) -> Dict[str, float]:
    raw_values: Dict[str, float] = {}

    with result_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            match = _POWER_PATTERN.match(line)
            if match is None:
                continue

            key = match.group(1)
            if key in raw_values:
                continue
            raw_values[key] = float(match.group(2))

    if not raw_values:
        return {}

    leakage = raw_values.get("Total Leakage")
    if leakage is None:
        leakage = raw_values.get("Subthreshold Leakage", 0.0) + raw_values.get(
            "Gate Leakage", 0.0
        )

    dynamic = raw_values.get("Runtime Dynamic", 0.0)
    peak_dynamic = raw_values.get("Peak Dynamic", dynamic)
    return {
        "power_total": leakage + dynamic,
        "power_dynamic": dynamic,
        "power_leakage": leakage,
        "power_peak_dynamic": peak_dynamic,
    }


def _parse_ptrace_summary(result_file: Path) -> Dict[str, float]:
    trace_file = result_file.parent / "out.ptrace"
    if not trace_file.exists():
        return {}

    with trace_file.open("r", encoding="utf-8") as handle:
        lines = [line.strip() for line in handle if line.strip()]

    if len(lines) < 2:
        return {}

    try:
        values = [float(token) for token in lines[1].split()]
    except ValueError:
        return {}

    if not values:
        return {}

    total_power = sum(values)
    return {
        "power_total": total_power,
        # This McPAT fork emits per-block power trace values in `out.ptrace`.
        # We conservatively use the summed trace as the backend's comparable
        # power figure until verbose leakage/dynamic breakdown is enabled.
        "power_dynamic": total_power,
        "power_leakage": 0.0,
        "power_peak_dynamic": max(values),
    }


def parse_mcpat_summary(result_file: Path) -> Dict[str, float]:
    verbose_summary = _parse_verbose_summary(result_file)
    if verbose_summary:
        return verbose_summary

    ptrace_summary = _parse_ptrace_summary(result_file)
    if ptrace_summary:
        return ptrace_summary

    return {
        "power_total": 0.0,
        "power_dynamic": 0.0,
        "power_leakage": 0.0,
        "power_peak_dynamic": 0.0,
    }
