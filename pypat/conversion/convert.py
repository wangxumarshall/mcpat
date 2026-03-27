import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .gem5_to_mcpat import run_conversion
from pypat.parsers.mcpat_text import parse_mcpat_summary


def gen_dirs(target_dir: Path) -> Dict[str, Path]:
    stats_txt = target_dir / "stats.txt"
    stats_h5 = target_dir / "stats.h5"

    if stats_txt.exists():
        stats_file = stats_txt
    elif stats_h5.exists():
        stats_file = stats_h5
    else:
        raise FileNotFoundError(f"No stats.txt or stats.h5 found in {target_dir}")

    return {
        "base_path": target_dir,
        "config_file": target_dir / "config.json",
        "stats_file": stats_file,
    }


def run_mcpat(
    mcpat_binary: Path,
    target: Path,
    mcpat_input: Path,
    print_level: int,
    opt_for_clk: int,
) -> Path:
    if not mcpat_binary.exists():
        raise FileNotFoundError(
            f"McPAT binary not found at {mcpat_binary}. Build it first or pass --mcpat-binary."
        )

    mcpat_output = target / "mcpat_results.txt"
    command = [
        str(mcpat_binary.resolve()),
        "-infile",
        str(mcpat_input.resolve()),
        "-print_level",
        str(print_level),
        "-opt_for_clk",
        str(opt_for_clk),
    ]

    with mcpat_output.open("w") as out_file:
        try:
            subprocess.run(
                command,
                check=True,
                cwd=target,
                stdout=out_file,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as exc:
            out_file.flush()
            log_excerpt = mcpat_output.read_text(encoding="utf-8", errors="replace")
            excerpt = log_excerpt[:1200].strip()
            raise RuntimeError(
                f"McPAT failed with exit code {exc.returncode}. "
                f"See {mcpat_output}. Output starts with:\n{excerpt}"
            ) from exc

    return mcpat_output


def run(
    target_dir: Union[Path, str],
    template: Optional[Path] = None,
    outfile: Optional[Path] = None,
    template_profile: str = "auto",
    print_level: int = 1,
    opt_for_clk: int = 0,
    mcpat_binary: Optional[Path] = None,
) -> Dict[str, Any]:
    if isinstance(target_dir, str):
        target_dir = Path(target_dir)

    dirs = gen_dirs(target_dir)
    repo_root = Path(__file__).resolve().parents[2]
    mcpat_input = outfile if outfile is not None else target_dir / "conv.xml"
    mcpat_binary = mcpat_binary if mcpat_binary is not None else repo_root / "mcpat"

    selected_profile = run_conversion(
        stats_file=dirs["stats_file"],
        config_file=dirs["config_file"],
        outfile=mcpat_input,
        template=template,
        template_profile=template_profile,
    )

    mcpat_output = run_mcpat(
        mcpat_binary=mcpat_binary,
        target=dirs["base_path"],
        mcpat_input=mcpat_input,
        print_level=print_level,
        opt_for_clk=opt_for_clk,
    )

    power_summary = parse_mcpat_summary(mcpat_output)

    return {
        "mcpat_input": mcpat_input,
        "mcpat_output": mcpat_output,
        "mcpat_area_output": target_dir / "out.area",
        "mcpat_power_trace": target_dir / "out.ptrace",
        "stats_file": dirs["stats_file"],
        "config_file": dirs["config_file"],
        "template_profile": selected_profile,
        **power_summary,
    }
