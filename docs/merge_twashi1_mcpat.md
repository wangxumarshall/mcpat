# Merge Notes: `Twashi1/mcpat`

## Source

- Repository: `https://github.com/Twashi1/mcpat.git`
- Reviewed branch: `upstream_master`
- Reviewed source commit: `ef5ce00f9228a69f3e40c025b125edd9e5cedbe4`

## What Was Integrated

The relevant upstream changes were small and concentrated in
[cacti/technology.cc](../cacti/technology.cc):

- add direct handling for the 14nm technology node
- relax one low-Vdd fatal exit into a warning so exploratory runs can continue

## Effect

- XML and CACTI configurations around 14nm no longer fall through the older
  node-selection logic.
- User-defined low-Vdd experiments can continue past the early warning site
  instead of terminating immediately.

## Usage

No new flag is required. The change applies automatically when a configuration
selects a technology node in the 14nm range or uses aggressive Vdd values.

## Validation

- The logic was ported directly into the active technology path.
- Full repository build validation remains blocked on the current `arm64` host
  because the makefile still targets x86/32-bit flags.
