# Multi-Source Integration Notes (2026-03-26)

## Summary

This repository round integrated modifications from the following upstream
repositories into local `master`:

- `alexmanle/pypat`
- `JaimeRoelandts/McPat_Sniper`
- `RY5228/mcpat-research`
- `TtitiO/mcpat-customized`
- `Twashi1/mcpat`
- `Ziheng-W/mcpat`

The integration was intentionally done source-by-source instead of mechanically
merging every branch. Some repositories were close McPAT forks and could be
merged or hand-ported directly; others were tool wrappers that would have
duplicated this repository's source tree if imported verbatim.

## Current Source Map

The main execution path of this repository is:

- [main.cc](../main.cc)
  parses command-line arguments, loads XML input, and drives `Processor`.
- [processor.cc](../processor.cc)
  assembles the top-level chip model and aggregates area/power across cores,
  caches, NoC, memory controllers, and I/O controllers.
- [processor.h](../processor.h)
  exposes the newer decoupled initialization/computation flow plus dump helpers
  used by trace-style execution.
- [core.h](../core.h)
  describes the core sub-hierarchy used by McPAT.
- [XML_Parse.cc](../XML_Parse.cc)
  maps XML interface data into internal runtime structures.
- [array.cc](../array.cc), [cacti/io.cc](../cacti/io.cc), and
  [cacti/technology.cc](../cacti/technology.cc)
  contain the CACTI-side memory and technology modeling paths where several of
  the imported research fork changes landed.

## Imported Work By Source

- `Ziheng-W/mcpat`
  brought decoupled initialization/computation, `-trace` continuous simulation,
  `out.area` / `out.ptrace` dumping, and the `custom_block.*` extension hook.
- `Twashi1/mcpat`
  added 14nm technology-node handling and relaxed one low-Vdd fatal exit into a
  warning so exploratory runs can continue.
- `RY5228/mcpat-research`
  lowered the minimum accepted cache size from 64 to 16 in the CACTI path.
- `JaimeRoelandts/McPat_Sniper`
  contributed LMDB-backed memoization for repeated CACTI solves; only this
  modular part was ported to avoid large XML parser conflicts.
- `alexmanle/pypat`
  was integrated as an in-repo Python toolchain under [pypat](../pypat),
  supporting gem5 `stats.txt` and `stats.h5` inputs plus direct invocation of
  the local `mcpat` binary.
- `TtitiO/mcpat-customized`
  contributed the batch-run workflow that is now generalized as
  [run_mcpat_batch.sh](../run_mcpat_batch.sh).

## User-Facing Entry Points

### Native McPAT

```bash
./mcpat -infile <input.xml> -print_level 5 -opt_for_clk 1
```

### Continuous trace simulation

```bash
./mcpat -trace -infile <input.xml> -print_level 5 -opt_for_clk 1
```

After startup, type:

- another XML path to recompute on a new interface file
- `repeat` to recompute the previous file
- `exit` to stop

### Existing Gem5 parser flow

```bash
bash run_mcpat.sh 2 0 McPAT_out
```

### New `pypat` flow

```bash
python3 -m pypat /path/to/m5out --print-level 2 --opt-for-clk 0
```

Expected gem5 directory contents:

- `config.json`
- `stats.txt` or `stats.h5`

### Batch-run many XML inputs

```bash
PRINT_LEVEL=5 OPT_FOR_CLK=1 bash run_mcpat_batch.sh ./McPAT_out
```

The batch script walks a directory tree, runs `mcpat` on each XML, and writes
`*.area` / `*.ptrace` next to each input. If the XML name starts with
`mcpat_in`, the output prefix is rewritten to `mcpat_out`.

### Optional CACTI memoization

```bash
make opt CACHE=1
```

This enables LMDB-backed result caching for repeated CACTI solves. Without
`CACHE=1`, the repository behaves as before.

## Validation Performed

The following validations were executed after this integration round:

- `python3 -m py_compile ...`
  covering the new `pypat` package and
  [gem5_mcpat_parser/Gem5McPATParser_custom.py](../gem5_mcpat_parser/Gem5McPATParser_custom.py)
  Result: passed
- `python3 -m pypat --help`
  Result: passed
- `python3 -m pypat.search_h5 --help`
  Result: passed
- `bash -n run_mcpat.sh run_mcpat_batch.sh`
  Result: passed
- `g++ -std=c++17 -DENABLE_MEMOIZATION -I/tmp/lmdb_stub -Icacti -fsyntax-only cacti/results_db.cc`
  Result: passed
  Note: the host machine did not provide LMDB headers, so a temporary stub was
  used for syntax-only validation of the new memoization module.
- `make opt`
  Result: failed on the current host because
  [mcpat.mk](../mcpat.mk)
  still uses x86/32-bit-oriented flags (`-m32 -msse2 -mfpmath=sse`) while the
  local machine is `arm64-apple-darwin`

## Known Limitations

- The local host still cannot build the repository with the default make flags
  on Apple Silicon.
- `CACHE=1` requires a real LMDB installation at build time.
- The new `pypat` package depends on `h5py` for `.h5` support.
- `TtitiO/mcpat-customized` was intentionally integrated as a generalized batch
  workflow, not as a second large-scale core-code merge, because its code base
  largely overlaps `Ziheng-W/mcpat`.

## Source-Specific Notes

- [docs/merge_alexmanle_pypat.md](./merge_alexmanle_pypat.md)
- [docs/merge_jaime_roelandts_mcpat_sniper.md](./merge_jaime_roelandts_mcpat_sniper.md)
- [docs/merge_ry5228_mcpat_research.md](./merge_ry5228_mcpat_research.md)
- [docs/merge_ttitio_mcpat_customized.md](./merge_ttitio_mcpat_customized.md)
- [docs/merge_twashi1_mcpat.md](./merge_twashi1_mcpat.md)
- [docs/merge_ziheng_w_mcpat.md](./merge_ziheng_w_mcpat.md)
- Existing earlier integration:
  [docs/merge_zhaoyu_jin_mcpat_gem5.md](./merge_zhaoyu_jin_mcpat_gem5.md)
