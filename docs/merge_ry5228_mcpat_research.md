# Merge Notes: `RY5228/mcpat-research`

## Source

- Repository: `https://github.com/RY5228/mcpat-research.git`
- Reviewed source commit: `7ef61544f6e746b8bd231c885b0538b2b8992107`

## What Was Integrated

This repository contributed a focused CACTI behavior tweak:

- lower the minimum accepted cache size from `64` to `16`

The change was ported into:

- [array.cc](../array.cc)
- [cacti/io.cc](../cacti/io.cc)

## Effect

Smaller cache-like structures that were previously rejected below 64 bytes are
now accepted down to 16 bytes in the relevant CACTI/McPAT path.

## Usage

No new command-line flag is required. The behavior change is automatic once the
repository is built.

## Validation

- Code was ported directly into the active CACTI path and reviewed in place.
- No separate full binary build succeeded on this host because the repository's
  default make flags still target x86/32-bit on an `arm64` machine.
