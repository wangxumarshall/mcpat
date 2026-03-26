#!/usr/bin/env bash

set -euo pipefail

input_root="${1:-./McPAT_out}"
print_level="${PRINT_LEVEL:-5}"
opt_for_clk="${OPT_FOR_CLK:-1}"

if [[ ! -d "${input_root}" ]]; then
  echo "Input directory not found: ${input_root}" >&2
  exit 1
fi

xml_files=()
while IFS= read -r xml_file; do
  xml_files+=("${xml_file}")
done < <(find "${input_root}" -type f -name '*.xml' | sort)

if [[ "${#xml_files[@]}" -eq 0 ]]; then
  echo "No XML inputs found under ${input_root}" >&2
  exit 1
fi

for xml_file in "${xml_files[@]}"; do
  xml_dir="$(dirname "${xml_file}")"
  xml_name="$(basename "${xml_file}" .xml)"
  output_stem="${xml_name/mcpat_in/mcpat_out}"

  echo "Running mcpat on ${xml_file}"
  ./mcpat -infile "${xml_file}" -print_level "${print_level}" -opt_for_clk "${opt_for_clk}"

  if [[ -f out.area ]]; then
    mv out.area "${xml_dir}/${output_stem}.area"
  fi
  if [[ -f out.ptrace ]]; then
    mv out.ptrace "${xml_dir}/${output_stem}.ptrace"
  fi
done
