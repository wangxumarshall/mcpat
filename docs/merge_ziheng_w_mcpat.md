# Merge Notes: `Ziheng-W/mcpat`

## Source

- Repository: `https://github.com/Ziheng-W/mcpat.git`
- Reviewed source commit: `758d196e54719c2f123e51cff9b722f02bac940a`
- Local merge commit: `1ec37b6` (`Merge Ziheng-W mcpat updates`)

## What Was Integrated

This was the largest source-code integration in the round and was merged into
local `master`.

Key imported behavior:

- decoupled initialization and computation inside `Processor`
- `-trace` mode for consecutive simulation runs
- summarized `out.area` and `out.ptrace` dump generation
- `custom_block.*` extension hook
- additional ARM-based example XML

## Primary Files Affected

- [main.cc](../main.cc)
- [processor.h](../processor.h)
- [processor.cc](../processor.cc)
- [custom_block.h](../custom_block.h)
- [custom_block.cc](../custom_block.cc)
- [ProcessorDescriptionFiles/OoO_4_core_private_ArmBased.xml](../ProcessorDescriptionFiles/OoO_4_core_private_ArmBased.xml)

## Usage

Original one-shot mode still works:

```bash
./mcpat -infile <input.xml> -print_level 5 -opt_for_clk 1
```

Trace mode:

```bash
./mcpat -trace -infile <input.xml> -print_level 5 -opt_for_clk 1
```

Interactive commands after startup:

- `<new-file.xml>`: parse a new XML and recompute
- `repeat`: recompute the previous XML
- `exit`: stop the loop

The run also writes:

- `out.area`
- `out.ptrace`

## Local Notes

- This merge was accepted largely as an actual upstream merge, unlike some of
  the other repositories in this round.
- The imported `README.md` was kept alongside the repository's original
  [README](../README).

## Validation

- The merged code is present on the current local mainline and is referenced by
  later integrations, including the batch-run script that consumes
  `out.area` / `out.ptrace`.
- Full host build validation is still limited by the repository's x86/32-bit
  makefile flags on the current `arm64` machine.
