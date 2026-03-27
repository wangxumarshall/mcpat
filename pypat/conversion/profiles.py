from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Tuple

from .arm64_kunpeng920 import normalize_kunpeng920_config, normalize_kunpeng920_stats
from .templates import canonical_template_profile_name


def _parser_root() -> Path:
    return Path(__file__).resolve().parents[2] / "gem5_mcpat_parser"


def _profile_path(profile_name: str) -> Path:
    canonical = canonical_template_profile_name(profile_name)
    profile_map = {
        "arm64-kunpeng920": _parser_root() / "kunpeng920_profile.json",
    }
    if canonical not in profile_map:
        raise ValueError(f"Unsupported McPAT profile '{profile_name}'.")
    return profile_map[canonical]


def _contains_arm_signature(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_arm_signature(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_arm_signature(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return any(
            token in lowered
            for token in ["armisa", "aarch64", "armv8", "arm", "tsv110", "kunpeng"]
        )
    return False


def infer_template_profile(config: Dict[str, Any]) -> str:
    if _contains_arm_signature(config):
        return "arm64-kunpeng920"
    return "x86"


def load_profile(profile_name: str) -> Dict[str, Any]:
    canonical = canonical_template_profile_name(profile_name)
    if canonical == "x86":
        return {}
    path = _profile_path(profile_name)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_gem5_config(
    config: Dict[str, Any], template_profile: str = "auto"
) -> Tuple[Dict[str, Any], str]:
    normalized: Dict[str, Any] = copy.deepcopy(config)

    if "board" in normalized and "system" not in normalized:
        normalized["system"] = copy.deepcopy(normalized["board"])
    elif "system" in normalized and "board" not in normalized:
        normalized["board"] = copy.deepcopy(normalized["system"])

    selected_profile = (
        infer_template_profile(normalized)
        if template_profile == "auto"
        else canonical_template_profile_name(template_profile)
    )

    normalized["profile"] = load_profile(selected_profile)
    if selected_profile == "arm64-kunpeng920":
        normalized = normalize_kunpeng920_config(normalized, normalized["profile"])
    normalized["selected_template_profile"] = selected_profile
    return normalized, selected_profile


def normalize_gem5_stats(
    stats: Dict[int, Dict[str, str]],
    config: Dict[str, Any],
    template_profile: str,
) -> Dict[int, Dict[str, str]]:
    canonical = canonical_template_profile_name(template_profile)
    if canonical == "arm64-kunpeng920":
        return normalize_kunpeng920_stats(stats, config)
    return stats
