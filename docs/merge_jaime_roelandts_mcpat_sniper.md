# Merge Notes: `JaimeRoelandts/McPat_Sniper`

## Source

- Repository: `https://github.com/JaimeRoelandts/McPat_Sniper.git`
- Reviewed branch: `sniper`
- Reviewed source commit: `3ccee758c035961be2dfda9b4c82ba79886eca04`

## Integration Strategy

This upstream branch contains several large-scale changes, including a full XML
parsing rewrite and many CACTI modifications. A direct branch merge conflicted
heavily with the current local mainline, especially after the `Ziheng-W/mcpat`
integration.

The valuable, low-conflict feature here was LMDB-backed memoization for CACTI
solve results. That feature was ported modularly instead of merging the full
branch.

## Imported Files And Hooks

- New files:
  - [cacti/results_db.h](../cacti/results_db.h)
  - [cacti/results_db.cc](../cacti/results_db.cc)
- Hooked into:
  - [cacti/io.cc](../cacti/io.cc)
  - [mcpat.mk](../mcpat.mk)

## Behavior

When `CACHE=1` is enabled at build time, McPAT now:

1. serializes the effective `InputParameter`
2. looks for a cached `uca_org_t` result in LMDB
3. reuses it if present
4. otherwise runs the normal solve path and stores the result

Without `CACHE=1`, behavior remains unchanged.

## Usage

Install LMDB development headers/libraries, then build with:

```bash
make opt CACHE=1
```

At runtime, the cache database is created as:

```text
${TMPDIR:-${TEMPDIR:-/tmp}}/mcpat-$USER.db
```

## Local Integration Adjustments

- Only the memoization feature was imported; the XML parser rewrite was not.
- C++17 is enabled only when `CACHE=1` is requested, because `results_db.*`
  uses `std::filesystem`.
- The port adds safety fallbacks so LMDB initialization failure disables cache
  use instead of crashing the process.

## Validation

- `g++ -std=c++17 -DENABLE_MEMOIZATION -I/tmp/lmdb_stub -Icacti -fsyntax-only cacti/results_db.cc`
  Result: passed
- Real `make opt CACHE=1`
  Result: not executed successfully on this host because LMDB headers were not
  installed locally and the repository's default make flags also target x86/32-bit

## Known Limitation

This integration only ports the memoization subsystem, not the full upstream
Sniper branch behavior.
