# Merge Notes: `Zhaoyu-Jin/mcpat` `mcpat_gem5`

## Summary

This repository merged the `mcpat_gem5` branch from
`https://github.com/Zhaoyu-Jin/mcpat.git` into local `master` with merge
commit `c4b53d5`.

The imported work does not modify McPAT's core C++ power/area model. Instead,
it adds a Gem5-to-McPAT XML generation flow so Gem5 `config.json` and
`stats.txt` can be converted into an McPAT input XML and then consumed by the
existing `mcpat` binary.

## Why This Merge Was Needed

The local repository already shared the same `master` base as the upstream
repository. The real delta lived in upstream branch `mcpat_gem5`, which adds:

- A Python parser for Gem5 output
- An McPAT XML template targeting an x86 OoO Gem5 configuration
- A convenience script to generate XML and invoke `mcpat`
- Minor ignore-file updates

## Relevant Source Layout

The merge was reviewed against the existing project structure:

- [main.cc](../main.cc)
  parses CLI arguments, loads XML, and instantiates `Processor`.
- [processor.cc](../processor.cc)
  is the top-level system assembly path. It builds `Core`, `SharedCache`,
  `MemoryController`, `NoC`, and I/O controller models and accumulates
  area/power/runtime power.
- [core.h](../core.h)
  shows the core hierarchy used by McPAT, including IFU, LSU, MMU, rename,
  scheduler, register file, and execution units.
- [sharedcache.h](../sharedcache.h)
  defines the shared cache and directory-side modeling components.

This review confirmed that the upstream merge only adds a front-end input flow
and does not alter the existing modeling implementation.

## Imported Files

The merge imported or updated the following user-facing files:

- [gem5_mcpat_parser/Gem5McPATParser_custom.py](../gem5_mcpat_parser/Gem5McPATParser_custom.py)
- [gem5_mcpat_parser/template_x86.xml](../gem5_mcpat_parser/template_x86.xml)
- [gem5_mcpat_parser/README](../gem5_mcpat_parser/README)
- [run_mcpat.sh](../run_mcpat.sh)
- [.gitignore](../.gitignore)

## Local Integration Adjustments

The upstream changes were merged with a few small integration fixes so the new
flow is easier to use in this repository:

1. [run_mcpat.sh](../run_mcpat.sh)
   was hardened:
   - added `#!/usr/bin/env bash`
   - added `set -euo pipefail`
   - added automatic creation of `McPAT_input/` and `results/`
   - added safer quoting
   - added default values for `print_level` and `opt_for_clk`
   - added `GEM5_OUT_DIR` environment override support
2. [gem5_mcpat_parser/Gem5McPATParser_custom.py](../gem5_mcpat_parser/Gem5McPATParser_custom.py)
   was adjusted to use raw-string regex literals in two locations to eliminate
   Python `SyntaxWarning`s during compilation.
3. [.gitignore](../.gitignore)
   was extended for:
   - `McPAT_input/`
   - `results/`
   - `obj_dbg/`
   - `__pycache__/`
   - `*.pyc`

## How The New Flow Works

The new Gem5 integration path is:

1. Build or provide the `mcpat` binary as usual.
2. Run the Python parser with Gem5 `config.json` and `stats.txt`.
3. Generate an McPAT XML input file in `McPAT_input/mcpat_in.xml`.
4. Invoke `./mcpat -infile ...` on that generated XML.

The convenience wrapper is [run_mcpat.sh](../run_mcpat.sh).

## Usage

### Direct script usage

```bash
bash run_mcpat.sh <print_level> <opt_for_clk> <output_name>
```

Example:

```bash
bash run_mcpat.sh 2 0 McPAT_out
```

This writes:

- generated input XML to `McPAT_input/mcpat_in.xml`
- McPAT textual output to `results/McPAT_out`

### Override Gem5 output directory

```bash
GEM5_OUT_DIR=/path/to/m5out bash run_mcpat.sh 2 0 McPAT_out
```

The script expects the Gem5 directory to contain:

- `config.json`
- `stats.txt`

### Direct parser usage

```bash
python3 gem5_mcpat_parser/Gem5McPATParser_custom.py \
  -c /path/to/m5out/config.json \
  -s /path/to/m5out/stats.txt \
  -t gem5_mcpat_parser/template_x86.xml \
  -o McPAT_input/mcpat_in.xml
```

Then run:

```bash
./mcpat -infile McPAT_input/mcpat_in.xml -print_level 2 -opt_for_clk 0
```

## Validation Performed

The following checks were run after the merge:

- `python3 -m py_compile gem5_mcpat_parser/Gem5McPATParser_custom.py`
  Result: passed
- `bash -n run_mcpat.sh`
  Result: passed
- `make opt`
  Result: failed on the current machine because the repository still uses
  x86/32-bit-oriented build flags in
  [mcpat.mk](../mcpat.mk),
  specifically `-m32 -msse2 -mfpmath=sse`, while the local environment is
  `arm64-apple-darwin`

## Known Limitations

- The imported template and stat-name adaptation logic are tailored for a
  specific Gem5 output structure and x86 OoO-style configuration.
- The merge does not make McPAT itself cross-platform; the existing build
  system may still require updates for Apple Silicon or other non-x86 hosts.
- The parser performs expression substitution with Python `eval`, so template
  expressions should be treated as trusted repository content.

## Commit History

- Imported feature merge:
  - `c4b53d5` `Merge Zhaoyu-Jin mcpat_gem5 into master`

## Recommended Next Steps

- If this repository will be built on Apple Silicon, update
  [mcpat.mk](../mcpat.mk)
  to support non-x86 compilation flags.
- If multiple Gem5 configurations are expected, add more templates and parser
  mapping tests for those layouts.
