#!/usr/bin/env bash

set -euo pipefail

gem5_out_dir="${GEM5_OUT_DIR:-../gem5_with_mcpat/runahead_gem5/m5out}"
parser_dir="./gem5_mcpat_parser"
mcpat_input_path="./McPAT_input/mcpat_in.xml"
output_file="./results/${3:-McPAT_out}"
template_path="${MCPAT_TEMPLATE:-}"
template_profile="${MCPAT_TEMPLATE_PROFILE:-auto}"

mkdir -p "$(dirname "${mcpat_input_path}")" "$(dirname "${output_file}")"

parser_args=(
  -c "${gem5_out_dir}/config.json"
  -s "${gem5_out_dir}/stats.txt"
  -o "${mcpat_input_path}"
)

if [[ -n "${template_path}" ]]; then
  parser_args+=(-t "${template_path}")
else
  parser_args+=(--template-profile "${template_profile}")
fi

python3 "${parser_dir}/Gem5McPATParser_custom.py" "${parser_args[@]}"

./mcpat -infile "${mcpat_input_path}" -print_level "${1:-2}" -opt_for_clk "${2:-0}" | tee "${output_file}"

echo "Results in ${output_file}"
