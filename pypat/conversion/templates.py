from pathlib import Path


_PROFILE_ALIASES = {
    "auto": "auto",
    "arm64": "arm64-kunpeng920",
    "arm64-kunpeng920": "arm64-kunpeng920",
    "arm64_kunpeng920": "arm64-kunpeng920",
    "kunpeng920": "arm64-kunpeng920",
    "x86": "x86",
}

_PROFILE_TEMPLATES = {
    "x86": "template_x86.xml",
    "arm64-kunpeng920": "template_arm64_kunpeng920.xml",
}


def canonical_template_profile_name(profile_name: str) -> str:
    lowered = profile_name.strip().lower()
    if lowered not in _PROFILE_ALIASES:
        raise ValueError(f"Unsupported McPAT template profile '{profile_name}'.")
    return _PROFILE_ALIASES[lowered]


def default_template_path(profile_name: str = "x86") -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    canonical = canonical_template_profile_name(profile_name)
    if canonical == "auto":
        canonical = "x86"
    return repo_root / "gem5_mcpat_parser" / _PROFILE_TEMPLATES[canonical]
