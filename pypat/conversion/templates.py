from pathlib import Path


def default_template_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "gem5_mcpat_parser" / "template_x86.xml"
