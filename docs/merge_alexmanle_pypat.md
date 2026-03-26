# Merge Notes: `alexmanle/pypat`

## Source

- Repository: `https://github.com/alexmanle/pypat.git`
- Reviewed source commit: `092ef0a`

## What Was Integrated

This upstream repository is not a pure McPAT fork. It is a Python wrapper that:

- reads gem5 `config.json`
- reads gem5 `stats.txt` or `stats.h5`
- renders an McPAT XML input file
- runs the local `mcpat` binary

To avoid duplicating an entire second McPAT source tree, only the wrapper/tool
layer was imported into this repository under [pypat](../pypat).

## Imported Files

- [pypat/__main__.py](../pypat/__main__.py)
- [pypat/conversion/gem5_to_mcpat.py](../pypat/conversion/gem5_to_mcpat.py)
- [pypat/conversion/convert.py](../pypat/conversion/convert.py)
- [pypat/conversion/templates.py](../pypat/conversion/templates.py)
- [pypat/parsers/csv_parse.py](../pypat/parsers/csv_parse.py)
- [pypat/parsers/h5_parse.py](../pypat/parsers/h5_parse.py)
- [pypat/parsers/h5_merge.py](../pypat/parsers/h5_merge.py)
- [pypat/search_h5.py](../pypat/search_h5.py)
- [pypat/README.md](../pypat/README.md)

## Local Integration Adjustments

- The wrapper reuses this repository's existing
  [gem5_mcpat_parser/template_x86.xml](../gem5_mcpat_parser/template_x86.xml)
  as the default template, instead of importing a second large inline template.
- XML retagging for a few special fields was moved from shell `sed -i` calls to
  pure Python so the flow works more reliably on macOS.
- The subprocess invocation was fixed to pass McPAT arguments as separate
  command-line tokens.
- Extra CLI options were added so users can override template, output XML path,
  print level, optimization mode, and binary path directly.

## Usage

```bash
python3 -m pypat /path/to/m5out
```

Example with explicit options:

```bash
python3 -m pypat /path/to/m5out \
  --template gem5_mcpat_parser/template_x86.xml \
  --outfile /path/to/m5out/conv.xml \
  --print-level 2 \
  --opt-for-clk 0
```

Optional helper tools:

- `python3 -m pypat.search_h5 <stats.h5> <query>`
- `python3 -m pypat.parsers.h5_merge <out.h5> <in1.h5> <in2.h5> ...`
- `python3 -m pypat.parsers.h5_parse <input_dir> <group_name> <output.h5>`
- `python3 -m pypat.parsers.csv_parse <input_dir> <output.csv>`

## Validation

- `python3 -m py_compile ...`
  Result: passed
- `python3 -m pypat --help`
  Result: passed
- `python3 -m pypat.search_h5 --help`
  Result: passed

## Dependency Note

`stats.h5` support requires Python package `h5py`.
