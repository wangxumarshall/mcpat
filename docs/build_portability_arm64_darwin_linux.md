# Build Portability Notes: arm64 / Darwin / Linux

## Summary

This patch updates the build system so the repository now builds on the current
`Darwin arm64` host and keeps Linux compatibility by selecting architecture
flags conditionally instead of hard-coding x86/32-bit options.

## What Changed

### Make logic

- [mcpat.mk](../mcpat.mk)
  no longer hard-codes:
  - `g++ -m32`
  - `gcc -m32`
  - `-msse2 -mfpmath=sse` on every platform
- [cacti/cacti.mk](../cacti/cacti.mk)
  received the same portability treatment for the standalone CACTI build.
- Both makefiles now:
  - use `c++` / `cc` by default
  - detect `uname -m`
  - keep SSE flags only for `x86_64/i386/i686`
  - avoid SSE flags on `arm64/aarch64`
  - keep `-pthread`
  - add Homebrew LMDB include/lib paths on Darwin when `CACHE=1`

### Source fixes exposed by clang/arm64

- [cacti/nuca.cc](../cacti/nuca.cc)
  - removed a duplicate default argument from the constructor definition
  - fixed a bank-contention array dimension mismatch
  - fixed a broken debug-print loop
- [cacti/powergating.cc](../cacti/powergating.cc)
  now returns a value from `Sleep_tx::compute_penalty()`
- [cacti/crossbar.cc](../cacti/crossbar.cc)
  removed an accidental vexing-parse style declaration
- [XML_Parse.cc](../XML_Parse.cc)
  - fixed several default-initialization array writes that indexed past the end
  - fixed one `L3` power-gating default that was mistakenly written into `L2`

## Validation

Executed on the current host:

- `make opt`
  Result: passed
- `make clean && make opt`
  Result: passed
- `make -C cacti opt`
  Result: passed
- `make -C cacti clean && make -C cacti opt`
  Result: passed
- `./mcpat -h`
  Result: passed

Dry-run compatibility checks:

- `make -n -B UNAME_S=Linux UNAME_M=aarch64 opt`
  Result: no x86-only flags emitted
- `make -n -B UNAME_S=Linux UNAME_M=x86_64 opt`
  Result: SSE flags emitted only on x86_64
- `make -n -B -C cacti UNAME_S=Linux UNAME_M=aarch64 opt`
  Result: standalone CACTI path also avoids x86-only flags

## Remaining Notes

- `CACHE=1` still requires LMDB headers and libraries to be installed on the
  target machine.
- The repository still emits a number of compiler warnings on modern clang, but
  the default optimized build now completes successfully on `Darwin arm64`.
