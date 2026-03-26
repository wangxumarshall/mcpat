import subprocess
from pathlib import Path
from typing import Dict, Optional, Union

from .gem5_to_mcpat import run_conversion


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
        str(mcpat_binary),
        "-infile",
        str(mcpat_input.resolve()),
        "-print_level",
        str(print_level),
        "-opt_for_clk",
        str(opt_for_clk),
    ]

    with mcpat_output.open("w") as out_file:
        subprocess.run(command, check=True, stdout=out_file, stderr=subprocess.STDOUT)

    return mcpat_output


def run(
    target_dir: Union[Path, str],
    template: Optional[Path] = None,
    outfile: Optional[Path] = None,
    print_level: int = 1,
    opt_for_clk: int = 0,
    mcpat_binary: Optional[Path] = None,
) -> Dict[str, Path]:
    if isinstance(target_dir, str):
        target_dir = Path(target_dir)

    dirs = gen_dirs(target_dir)
    repo_root = Path(__file__).resolve().parents[2]
    mcpat_input = outfile if outfile is not None else target_dir / "conv.xml"
    mcpat_binary = mcpat_binary if mcpat_binary is not None else repo_root / "mcpat"

    run_conversion(
        stats_file=dirs["stats_file"],
        config_file=dirs["config_file"],
        outfile=mcpat_input,
        template=template,
    )

    mcpat_output = run_mcpat(
        mcpat_binary=mcpat_binary,
        target=dirs["base_path"],
        mcpat_input=mcpat_input,
        print_level=print_level,
        opt_for_clk=opt_for_clk,
    )

    return {
        "mcpat_input": mcpat_input,
        "mcpat_output": mcpat_output,
        "stats_file": dirs["stats_file"],
        "config_file": dirs["config_file"],
    }
