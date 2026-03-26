# Merge Notes: `TtitiO/mcpat-customized`

## Source

- Repository: `https://github.com/TtitiO/mcpat-customized.git`
- Reviewed source commit: `65662e7d669b444185f51b52604847020c1b4821`

## Integration Strategy

This repository overlaps heavily with `Ziheng-W/mcpat` and largely carries the
same core-code lineage. Its most useful unique addition was a shell workflow for
running `mcpat` over a batch of prepared XML files and collecting the generated
`out.area` / `out.ptrace` artifacts.

That workflow was generalized into a reusable script instead of merging another
large overlapping fork.

## Imported File

- [run_mcpat_batch.sh](../run_mcpat_batch.sh)

## Local Integration Adjustments

- The original hard-coded benchmark list was replaced with a recursive directory
  walk over any XML files under a chosen root.
- Output filenames are derived automatically from each input XML.
- The implementation was made portable to macOS's older Bash by avoiding
  `mapfile`.

## Usage

```bash
PRINT_LEVEL=5 OPT_FOR_CLK=1 bash run_mcpat_batch.sh ./McPAT_out
```

Behavior:

- finds all `*.xml` files under the input root
- runs `./mcpat -infile <xml>`
- moves `out.area` and `out.ptrace` next to that XML
- renames the prefix from `mcpat_in*` to `mcpat_out*` when applicable

## Validation

- `bash -n run_mcpat_batch.sh`
  Result: passed
