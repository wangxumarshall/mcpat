from __future__ import annotations

import copy
import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, Mapping


_MISSING = object()
_SIZE_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*([kmgt]?i?b)?\s*$", re.IGNORECASE)
_FREQ_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*([gmkh]?hz)?\s*$", re.IGNORECASE)
_SIZE_UNITS = {
    None: 1,
    "b": 1,
    "kb": 1000,
    "kib": 1024,
    "mb": 1000**2,
    "mib": 1024**2,
    "gb": 1000**3,
    "gib": 1024**3,
    "tb": 1000**4,
    "tib": 1024**4,
}
_FREQ_UNITS_TO_MHZ = {
    None: 1.0,
    "hz": 1.0 / 1_000_000.0,
    "khz": 1.0 / 1_000.0,
    "mhz": 1.0,
    "ghz": 1_000.0,
}


@dataclass(frozen=True)
class Kunpeng920McPATModel:
    system: Dict[str, Any]
    core: Dict[str, Any]
    caches: Dict[str, Dict[str, Any]]
    memory: Dict[str, Any]
    noc: Dict[str, Any]
    io: Dict[str, Dict[str, Any]]
    identity: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list):
        if not value:
            return None
        return _coerce_float(value[0])
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _coerce_int(value: Any) -> int | None:
    parsed = _coerce_float(value)
    if parsed is None:
        return None
    return int(round(parsed))


def _coerce_size_bytes(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(round(float(value)))
    if isinstance(value, list):
        if not value:
            return None
        return _coerce_size_bytes(value[0])
    if not isinstance(value, str):
        return None

    match = _SIZE_RE.match(value)
    if match is None:
        return None
    number = float(match.group(1))
    unit = match.group(2).lower() if match.group(2) is not None else None
    return int(round(number * _SIZE_UNITS[unit]))


def _coerce_frequency_mhz(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric <= 0:
            return None
        # Treat large bare numerics as Hz to tolerate gem5-ish raw frequencies.
        if numeric > 100_000.0:
            numeric *= _FREQ_UNITS_TO_MHZ["hz"]
        return int(round(numeric))
    if isinstance(value, list):
        if not value:
            return None
        return _coerce_frequency_mhz(value[0])
    if not isinstance(value, str):
        return None

    match = _FREQ_RE.match(value)
    if match is None:
        return None
    number = float(match.group(1))
    unit = match.group(2).lower() if match.group(2) is not None else None
    return int(round(number * _FREQ_UNITS_TO_MHZ[unit]))


def _clock_period_ps(clock_mhz: int) -> float:
    if clock_mhz <= 0:
        return 0.0
    return 1_000_000.0 / float(clock_mhz)


def _lookup_path(container: Any, path: str) -> Any:
    current = container
    for segment in path.split("."):
        if isinstance(current, list):
            if segment.isdigit():
                index = int(segment)
                if index >= len(current):
                    return _MISSING
                current = current[index]
            elif len(current) == 1 and isinstance(current[0], dict):
                current = current[0]
            else:
                return _MISSING

        if isinstance(current, dict):
            if segment not in current:
                return _MISSING
            current = current[segment]
            continue

        if isinstance(current, list):
            continue

        return _MISSING

    return current


def _any_path_exists(container: Any, paths: Iterable[str]) -> bool:
    return any(_lookup_path(container, path) is not _MISSING for path in paths)


def _first_config_value(
    container: Mapping[str, Any],
    parser,
    paths: Iterable[str],
    default: Any,
) -> Any:
    for path in paths:
        value = _lookup_path(container, path)
        if value is _MISSING:
            continue
        parsed = parser(value) if parser is not None else value
        if parsed is not None:
            return parsed
    return default


def _container_length(container: Any, paths: Iterable[str]) -> int | None:
    for path in paths:
        value = _lookup_path(container, path)
        if value is _MISSING:
            continue
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            numeric_keys = [key for key in value.keys() if str(key).isdigit()]
            if numeric_keys:
                return len(numeric_keys)
            if value:
                return len(value)
    return None


def _first_non_zero(*values: float) -> float:
    for value in values:
        if value > 0:
            return value
    return values[-1] if values else 0.0


def _to_stat_float(value: Any) -> float:
    parsed = _coerce_float(value)
    if parsed is None or math.isnan(parsed) or math.isinf(parsed):
        return 0.0
    return parsed


def _find_first_stat(raw_stats: Mapping[str, Any], aliases: Iterable[str]) -> float:
    for alias in aliases:
        if alias in raw_stats:
            return _to_stat_float(raw_stats[alias])
    for alias in aliases:
        for key, value in raw_stats.items():
            if key.endswith(alias):
                return _to_stat_float(value)
    return 0.0


def _sum_matching_suffixes(
    raw_stats: Mapping[str, Any], aliases: Iterable[str]
) -> float:
    matched_keys: set[str] = set()
    total = 0.0
    for alias in aliases:
        for key, value in raw_stats.items():
            if key in matched_keys:
                continue
            if key == alias or key.endswith(alias):
                matched_keys.add(key)
                total += _to_stat_float(value)
    return total


def _sum_matching_fragments(
    raw_stats: Mapping[str, Any], required_fragments: Iterable[str]
) -> float:
    fragments = [fragment.lower() for fragment in required_fragments]
    total = 0.0
    for key, value in raw_stats.items():
        lowered = key.lower()
        if all(fragment in lowered for fragment in fragments):
            total += _to_stat_float(value)
    return total


def _format_stat(value: float) -> str:
    if math.isclose(value, round(value), rel_tol=0.0, abs_tol=1e-9):
        return str(int(round(value)))
    return f"{value:.6f}"


def build_kunpeng920_model(
    config: Mapping[str, Any], profile: Mapping[str, Any]
) -> Kunpeng920McPATModel:
    default_clock_mhz = int(profile.get("target_core_clockrate_mhz", 2600))
    target_core_clockrate_mhz = _first_config_value(
        config,
        _coerce_frequency_mhz,
        (
            "system.clk_freq",
            "board.clk_freq",
            "system.clock",
            "board.clock",
        ),
        default_clock_mhz,
    )

    number_of_cores = _first_non_zero(
        float(
            _first_config_value(
                config,
                _coerce_int,
                (
                    "system.processor.num_cores",
                    "board.processor.num_cores",
                    "system.num_cores",
                    "board.num_cores",
                ),
                0,
            )
        ),
        float(
            _container_length(
                config,
                (
                    "system.processor.cores",
                    "board.processor.cores",
                    "system.processor.o3",
                    "board.processor.o3",
                    "system.cpu",
                    "board.cpu",
                ),
            )
            or 0
        ),
        float(profile.get("number_of_cores", 64)),
    )
    number_of_cores = max(1, int(number_of_cores))

    number_hardware_threads = _first_non_zero(
        float(
            _first_config_value(
                config,
                _coerce_int,
                (
                    "system.processor.o3.0.core.numThreads",
                    "board.processor.o3.0.core.numThreads",
                    "system.processor.cores.0.core.numThreads",
                    "board.processor.cores.0.core.numThreads",
                    "system.cpu.0.numThreads",
                    "board.cpu.0.numThreads",
                ),
                0,
            )
        ),
        float(profile.get("number_hardware_threads", 1)),
    )
    number_hardware_threads = max(1, int(number_hardware_threads))

    cores_per_cluster = int(profile.get("cores_per_cluster", 4))
    default_clusters_per_die = int(profile.get("clusters_per_die", 8))
    default_compute_dies = int(profile.get("compute_dies", 2))
    explicit_cache_hierarchy = _any_path_exists(
        config,
        (
            "system.cache_hierarchy",
            "board.cache_hierarchy",
        ),
    )
    explicit_l3 = _any_path_exists(
        config,
        (
            "system.cache_hierarchy.l3_size",
            "board.cache_hierarchy.l3_size",
            "system.cache_hierarchy.llc_size",
            "board.cache_hierarchy.llc_size",
        ),
    )
    has_l3 = explicit_l3 or not explicit_cache_hierarchy

    number_of_clusters = max(1, math.ceil(number_of_cores / cores_per_cluster))
    number_of_l3s = number_of_clusters if has_l3 else 0
    compute_dies = (
        max(1, math.ceil(number_of_clusters / default_clusters_per_die))
        if has_l3
        else 0
    )
    number_of_nocs = (
        min(default_compute_dies, compute_dies) if compute_dies > 0 else 0
    )

    l1i_size = _first_config_value(
        config,
        _coerce_size_bytes,
        ("system.cache_hierarchy.l1i_size", "board.cache_hierarchy.l1i_size"),
        int(profile.get("l1i_size", 65536)),
    )
    l1d_size = _first_config_value(
        config,
        _coerce_size_bytes,
        ("system.cache_hierarchy.l1d_size", "board.cache_hierarchy.l1d_size"),
        int(profile.get("l1d_size", 65536)),
    )
    l2_size = _first_config_value(
        config,
        _coerce_size_bytes,
        ("system.cache_hierarchy.l2_size", "board.cache_hierarchy.l2_size"),
        int(profile.get("l2_size", 524288)),
    )
    l3_total_size = _first_config_value(
        config,
        _coerce_size_bytes,
        (
            "system.cache_hierarchy.l3_size",
            "board.cache_hierarchy.l3_size",
            "system.cache_hierarchy.llc_size",
            "board.cache_hierarchy.llc_size",
        ),
        int(profile.get("l3_total_size", profile.get("l3_size", 67108864))),
    )
    l3_slice_size = (
        max(1, int(math.ceil(l3_total_size / number_of_l3s)))
        if number_of_l3s > 0
        else 0
    )

    explicit_memory_channels = _first_config_value(
        config,
        _coerce_int,
        (
            "system.memory.num_channels",
            "board.memory.num_channels",
            "system.mem_channels",
            "board.mem_channels",
        ),
        None,
    )
    if explicit_memory_channels is None:
        default_number_mcs = int(profile.get("number_mcs", 2))
        default_channels_per_mc = int(profile.get("memory_channels_per_mc", 4))
        number_mcs = default_number_mcs
        memory_channels_per_mc = default_channels_per_mc
    else:
        if explicit_memory_channels <= 4:
            number_mcs = 1
            memory_channels_per_mc = explicit_memory_channels
        else:
            number_mcs = min(int(profile.get("number_mcs", 2)), explicit_memory_channels)
            memory_channels_per_mc = max(
                1, math.ceil(explicit_memory_channels / number_mcs)
            )

    system = {
        "number_of_cores": number_of_cores,
        "number_of_l1directories": 0,
        "number_of_l2directories": 0,
        "number_of_l2s": number_of_cores,
        "private_l2": int(profile.get("private_l2", 1)),
        "number_of_l3s": number_of_l3s,
        "number_of_nocs": number_of_nocs,
        "number_cache_levels": 3 if number_of_l3s > 0 else 2,
        "number_hardware_threads": number_hardware_threads,
        "machine_bits": int(profile.get("machine_bits", 64)),
        "virtual_address_width": int(profile.get("virtual_address_width", 64)),
        "physical_address_width": int(profile.get("physical_address_width", 52)),
        "virtual_memory_page_size": int(profile.get("virtual_memory_page_size", 4096)),
        "mcpat_tech_node_nm": int(profile.get("mcpat_tech_node_nm", 22)),
        "target_core_clockrate_mhz": target_core_clockrate_mhz,
        "clock_period_ps": _clock_period_ps(target_core_clockrate_mhz),
        "temperature_k": int(profile.get("temperature_k", 380)),
        "interconnect_projection_type": int(
            profile.get("interconnect_projection_type", 0)
        ),
        "device_type": int(profile.get("device_type", 0)),
        "longer_channel_device": int(profile.get("longer_channel_device", 0)),
        "power_gating": int(profile.get("power_gating", 0)),
        "clusters": number_of_clusters,
        "cores_per_cluster": cores_per_cluster,
        "compute_dies": compute_dies,
    }

    core = {
        "target_core_clockrate_mhz": target_core_clockrate_mhz,
        "clock_period_ps": system["clock_period_ps"],
        "vdd": int(profile.get("vdd", 0)),
        "instruction_length": int(profile.get("instruction_length", 32)),
        "opcode_width": int(profile.get("opcode_width", 16)),
        "micro_opcode_width": int(profile.get("micro_opcode_width", 8)),
        "machine_type": int(profile.get("machine_type", 0)),
        "fetch_width": int(profile.get("fetch_width", 4)),
        "decode_width": int(profile.get("decode_width", 4)),
        "issue_width": int(profile.get("issue_width", 4)),
        "commit_width": int(profile.get("commit_width", 4)),
        "fp_issue_width": int(profile.get("fp_issue_width", 2)),
        "prediction_width": int(profile.get("prediction_width", 1)),
        "pipelines_per_core": str(profile.get("pipelines_per_core", "3,2")),
        "pipeline_depth": str(profile.get("pipeline_depth", "13,17")),
        "alu_per_core": int(profile.get("alu_per_core", 3)),
        "mul_per_core": int(profile.get("mul_per_core", 1)),
        "fpu_per_core": int(profile.get("fpu_per_core", 2)),
        "instruction_buffer_size": int(profile.get("instruction_buffer_size", 16)),
        "decoded_stream_buffer_size": int(
            profile.get("decoded_stream_buffer_size", 16)
        ),
        "instruction_window_size": int(profile.get("instruction_window_size", 33)),
        "fp_instruction_window_size": int(
            profile.get("fp_instruction_window_size", 33)
        ),
        "rob_size": int(profile.get("rob_size", 128)),
        "archi_regs_irf_size": int(profile.get("archi_regs_irf_size", 31)),
        "archi_regs_frf_size": int(profile.get("archi_regs_frf_size", 32)),
        "phy_regs_irf_size": int(profile.get("phy_regs_irf_size", 160)),
        "phy_regs_frf_size": int(profile.get("phy_regs_frf_size", 160)),
        "store_buffer_size": int(profile.get("store_buffer_size", 32)),
        "load_buffer_size": int(profile.get("load_buffer_size", 32)),
        "memory_ports": int(profile.get("memory_ports", 2)),
        "ras_size": int(profile.get("ras_size", 31)),
        "itlb_entries": int(profile.get("itlb_entries", 32)),
        "dtlb_entries": int(profile.get("dtlb_entries", 32)),
        "btb_entries": int(profile.get("btb_entries", 64)),
    }

    caches = {
        "l1i": {
            "size_bytes": l1i_size,
            "block_size": int(profile.get("l1i_block_size", 64)),
            "assoc": int(profile.get("l1i_assoc", 4)),
            "latency_cycles": int(profile.get("l1i_latency", 3)),
            "mshrs": int(profile.get("l1i_mshrs", 8)),
        },
        "l1d": {
            "size_bytes": l1d_size,
            "block_size": int(profile.get("l1d_block_size", 64)),
            "assoc": int(profile.get("l1d_assoc", 4)),
            "latency_cycles": int(profile.get("l1d_latency", 4)),
            "mshrs": int(profile.get("l1d_mshrs", 8)),
        },
        "l2": {
            "size_bytes": l2_size,
            "block_size": int(profile.get("l2_block_size", 64)),
            "assoc": int(profile.get("l2_assoc", 8)),
            "latency_cycles": int(profile.get("l2_latency", 10)),
            "mshrs": int(profile.get("l2_mshrs", 16)),
        },
        "l3": {
            "size_bytes": l3_slice_size,
            "total_size_bytes": l3_total_size,
            "block_size": int(profile.get("l3_block_size", 64)),
            "assoc": int(profile.get("l3_assoc", 16)),
            "latency_cycles": int(profile.get("l3_latency", 36)),
            "mshrs": int(profile.get("l3_mshrs", 64)),
        },
    }

    memory = {
        "number_mcs": int(number_mcs),
        "memory_channels_per_mc": int(memory_channels_per_mc),
        "number_ranks": int(profile.get("number_ranks", 2)),
        "memory_clock_mhz": int(profile.get("memory_clock_mhz", 1466)),
        "ddr_data_rate_mtps": int(profile.get("ddr_data_rate_mtps", 2933)),
        "databus_width": int(profile.get("databus_width", 64)),
        "addressbus_width": int(profile.get("addressbus_width", 52)),
    }

    noc = {
        "input_ports": int(profile.get("noc_input_ports", 2)),
        "output_ports": int(profile.get("noc_output_ports", 2)),
        "flit_bits": int(profile.get("noc_flit_bits", 256)),
    }

    io = {
        "niu": {
            "number_units": int(profile.get("niu_units", 0)),
            "clockrate_mhz": int(profile.get("niu_clockrate_mhz", 350)),
            "duty_cycle": float(profile.get("niu_duty_cycle", 0.0)),
            "total_load_perc": float(profile.get("niu_total_load_perc", 0.0)),
        },
        "pcie": {
            "number_units": int(profile.get("pcie_units", 0)),
            "num_channels": int(profile.get("pcie_channels", 8)),
            "clockrate_mhz": int(profile.get("pcie_clockrate_mhz", 350)),
            "duty_cycle": float(profile.get("pcie_duty_cycle", 0.0)),
            "total_load_perc": float(profile.get("pcie_total_load_perc", 0.0)),
        },
        "flashc": {
            "number_flashcs": int(profile.get("flash_controllers", 0)),
            "peak_transfer_rate": int(profile.get("flash_peak_transfer_rate", 200)),
            "duty_cycle": float(profile.get("flash_duty_cycle", 0.0)),
            "total_load_perc": float(profile.get("flash_total_load_perc", 0.0)),
        },
    }

    return Kunpeng920McPATModel(
        system=system,
        core=core,
        caches=caches,
        memory=memory,
        noc=noc,
        io=io,
        identity={
            "profile_name": str(profile.get("profile_name", "arm64-kunpeng920")),
            "isa_name": str(profile.get("isa_name", "ARMv8.2-A")),
            "core_name": str(profile.get("core_name", "TaiShan V110-like")),
        },
    )


def normalize_kunpeng920_config(
    config: Mapping[str, Any], base_profile: Mapping[str, Any]
) -> Dict[str, Any]:
    normalized = copy.deepcopy(dict(config))
    profile = copy.deepcopy(dict(base_profile))
    model = build_kunpeng920_model(normalized, profile)
    flat_profile = profile
    flat_profile.update(
        {
            "target_core_clockrate_mhz": model.core["target_core_clockrate_mhz"],
            "clock_period_ps": model.core["clock_period_ps"],
            "number_hardware_threads": model.system["number_hardware_threads"],
            "number_of_cores": model.system["number_of_cores"],
            "number_of_l2s": model.system["number_of_l2s"],
            "private_l2": model.system["private_l2"],
            "number_of_l3s": model.system["number_of_l3s"],
            "number_of_nocs": model.system["number_of_nocs"],
            "number_cache_levels": model.system["number_cache_levels"],
            "l1i_size": model.caches["l1i"]["size_bytes"],
            "l1d_size": model.caches["l1d"]["size_bytes"],
            "l2_size": model.caches["l2"]["size_bytes"],
            "l3_size": model.caches["l3"]["size_bytes"],
            "l3_total_size": model.caches["l3"]["total_size_bytes"],
            "memory_clock_mhz": model.memory["memory_clock_mhz"],
            "number_mcs": model.memory["number_mcs"],
            "memory_channels_per_mc": model.memory["memory_channels_per_mc"],
            "niu_units": model.io["niu"]["number_units"],
            "niu_clockrate_mhz": model.io["niu"]["clockrate_mhz"],
            "pcie_units": model.io["pcie"]["number_units"],
            "pcie_channels": model.io["pcie"]["num_channels"],
            "pcie_clockrate_mhz": model.io["pcie"]["clockrate_mhz"],
            "flash_controllers": model.io["flashc"]["number_flashcs"],
        }
    )
    normalized["profile"] = flat_profile
    normalized["mcpat"] = model.to_dict()
    return normalized


def normalize_kunpeng920_stats(
    stats: Dict[int, Dict[str, str]], config: Mapping[str, Any]
) -> Dict[int, Dict[str, str]]:
    normalized = {index: dict(values) for index, values in stats.items()}
    root_stats = normalized.setdefault(0, {})
    profile = config.get("profile", {})
    issue_width = max(1, int(profile.get("issue_width", 4)))
    memory_ports = max(1, int(profile.get("memory_ports", 2)))

    total_instructions = _first_non_zero(
        _find_first_stat(root_stats, ("simInsts", "commitStats0.numInsts", "baseStats.numInsts")),
        _find_first_stat(root_stats, ("fetch2.totalInstructions",)),
        0.0,
    )
    total_ops = _first_non_zero(
        _find_first_stat(root_stats, ("simOps", "commitStats0.numOps", "baseStats.numOps")),
        total_instructions,
        0.0,
    )
    total_cycles = _first_non_zero(
        _find_first_stat(root_stats, ("baseStats.numCycles", "numCycles")),
        (
            _find_first_stat(root_stats, ("simTicks",))
            / max(float(profile.get("clock_period_ps", 1.0)), 1.0)
        ),
        0.0,
    )
    busy_cycles = total_cycles
    idle_cycles = max(0.0, total_cycles - busy_cycles)

    int_instructions = _first_non_zero(
        _find_first_stat(root_stats, ("commitStats0.numIntInsts",)),
        _find_first_stat(root_stats, ("fetch2.intInstructions",)),
        0.0,
    )
    fp_scalar_instructions = _first_non_zero(
        _find_first_stat(root_stats, ("commitStats0.numFpInsts",)),
        _find_first_stat(root_stats, ("fetch2.fpInstructions",)),
        0.0,
    )
    vec_instructions = _first_non_zero(
        _find_first_stat(root_stats, ("commitStats0.numVecInsts",)),
        _find_first_stat(root_stats, ("fetch2.vecInstructions",)),
        0.0,
    )
    fp_instructions = fp_scalar_instructions + vec_instructions

    branch_instructions = _first_non_zero(
        _find_first_stat(root_stats, ("fetchStats0.numBranches", "executeStats0.numBranches")),
        _sum_matching_suffixes(
            root_stats,
            (
                "commitStats0.committedControl::IsDirectControl",
                "commitStats0.committedControl::IsIndirectControl",
                "commitStats0.committedControl::IsCondControl",
                "commitStats0.committedControl::IsCall",
                "commitStats0.committedControl::IsReturn",
            ),
        ),
        0.0,
    )
    branch_mispredictions = _first_non_zero(
        _find_first_stat(root_stats, ("numBranchMispred", "condIncorrect")),
        _sum_matching_suffixes(root_stats, ("mispredict", "mispredicted")),
        0.0,
    )

    load_instructions = _first_non_zero(
        _find_first_stat(root_stats, ("commitStats0.numLoadInsts", "executeStats0.numLoadInsts")),
        _find_first_stat(root_stats, ("fetch2.loadInstructions",)),
        0.0,
    )
    store_instructions = _first_non_zero(
        _find_first_stat(root_stats, ("commitStats0.numStoreInsts", "executeStats0.numStoreInsts")),
        _find_first_stat(root_stats, ("fetch2.storeInstructions",)),
        max(
            0.0,
            _find_first_stat(root_stats, ("commitStats0.numMemRefs", "executeStats0.numMemRefs"))
            - load_instructions,
        ),
    )
    committed_instructions = _first_non_zero(
        _find_first_stat(root_stats, ("commitStats0.numInsts",)),
        total_instructions,
        0.0,
    )
    committed_int_instructions = _first_non_zero(int_instructions, committed_instructions)
    committed_fp_instructions = fp_instructions

    int_reg_reads = _first_non_zero(
        _find_first_stat(root_stats, ("executeStats0.numIntRegReads",)),
        max(1.0, int_instructions * 2.0) if int_instructions > 0 else 0.0,
        0.0,
    )
    int_reg_writes = _first_non_zero(
        _find_first_stat(root_stats, ("executeStats0.numIntRegWrites",)),
        int_instructions,
        0.0,
    )
    float_reg_reads = _first_non_zero(
        _find_first_stat(root_stats, ("executeStats0.numFpRegReads",)),
        0.0,
        0.0,
    ) + _find_first_stat(root_stats, ("executeStats0.numVecRegReads",))
    float_reg_writes = _first_non_zero(
        _find_first_stat(root_stats, ("executeStats0.numFpRegWrites",)),
        0.0,
        0.0,
    ) + _find_first_stat(root_stats, ("executeStats0.numVecRegWrites",))

    ialu_accesses = _first_non_zero(
        _find_first_stat(root_stats, ("executeStats0.numIntAluAccesses",)),
        int_instructions,
        0.0,
    )
    fpu_accesses = _first_non_zero(
        _find_first_stat(root_stats, ("executeStats0.numFpAluAccesses",))
        + _find_first_stat(root_stats, ("executeStats0.numVecAluAccesses",)),
        fp_instructions,
        0.0,
    )
    mul_accesses = _first_non_zero(
        _sum_matching_fragments(root_stats, ("committedinsttype::", "mult")),
        _sum_matching_fragments(root_stats, ("committedinsttype::", "div")),
        fpu_accesses * 0.25 if fpu_accesses > 0 else int_instructions * 0.05,
    )

    pipeline_duty_cycle = (
        min(1.0, committed_instructions / (total_cycles * issue_width))
        if total_cycles > 0
        else 0.0
    )
    lsu_duty_cycle = (
        min(1.0, (load_instructions + store_instructions) / (total_cycles * memory_ports))
        if total_cycles > 0
        else 0.0
    )

    icache_read_accesses = _first_non_zero(
        _find_first_stat(
            root_stats,
            ("icache.ReadReq_accesses::total", "icache.overallAccesses::total"),
        ),
        total_instructions,
        0.0,
    )
    icache_read_misses = _first_non_zero(
        _find_first_stat(
            root_stats,
            ("icache.ReadReq_misses::total", "icache.overallMisses::total"),
        ),
        0.0,
    )
    dcache_read_accesses = _first_non_zero(
        _find_first_stat(
            root_stats,
            ("dcache.ReadReq_accesses::total", "dcache.overallReadAccesses::total"),
        ),
        load_instructions,
        0.0,
    )
    dcache_write_accesses = _first_non_zero(
        _find_first_stat(
            root_stats,
            ("dcache.WriteReq_accesses::total", "dcache.overallWriteAccesses::total"),
        ),
        store_instructions,
        0.0,
    )
    dcache_read_misses = _first_non_zero(
        _find_first_stat(
            root_stats,
            ("dcache.ReadReq_misses::total", "dcache.overallReadMisses::total"),
        ),
        0.0,
    )
    dcache_write_misses = _first_non_zero(
        _find_first_stat(
            root_stats,
            ("dcache.WriteReq_misses::total", "dcache.overallWriteMisses::total"),
        ),
        0.0,
    )

    l2_read_accesses = _first_non_zero(
        _find_first_stat(
            root_stats,
            ("l2.ReadReq_accesses::total", "l2cache.ReadReq_accesses::total", "l2.overallAccesses::total"),
        ),
        dcache_read_misses,
        0.0,
    )
    l2_write_accesses = _first_non_zero(
        _find_first_stat(
            root_stats,
            ("l2.WriteReq_accesses::total", "l2cache.WriteReq_accesses::total"),
        ),
        dcache_write_misses,
        0.0,
    )
    l2_read_misses = _first_non_zero(
        _find_first_stat(
            root_stats,
            ("l2.ReadReq_misses::total", "l2cache.ReadReq_misses::total", "l2.overallMisses::total"),
        ),
        0.0,
    )
    l2_write_misses = _first_non_zero(
        _find_first_stat(
            root_stats,
            ("l2.WriteReq_misses::total", "l2cache.WriteReq_misses::total"),
        ),
        0.0,
    )

    l3_read_accesses = _first_non_zero(
        _find_first_stat(
            root_stats,
            ("l3.ReadReq_accesses::total", "l3cache.ReadReq_accesses::total", "l3.overallAccesses::total"),
        ),
        l2_read_misses,
        0.0,
    )
    l3_write_accesses = _first_non_zero(
        _find_first_stat(
            root_stats,
            ("l3.WriteReq_accesses::total", "l3cache.WriteReq_accesses::total"),
        ),
        l2_write_misses,
        0.0,
    )
    l3_read_misses = _first_non_zero(
        _find_first_stat(
            root_stats,
            ("l3.ReadReq_misses::total", "l3cache.ReadReq_misses::total", "l3.overallMisses::total"),
        ),
        0.0,
    )
    l3_write_misses = _first_non_zero(
        _find_first_stat(
            root_stats,
            ("l3.WriteReq_misses::total", "l3cache.WriteReq_misses::total"),
        ),
        0.0,
    )

    memory_reads = _first_non_zero(
        _sum_matching_suffixes(root_stats, ("mem_ctrl.readReqs", "dram.readBursts", "readReqs")),
        l3_read_misses,
        0.0,
    )
    memory_writes = _first_non_zero(
        _sum_matching_suffixes(root_stats, ("mem_ctrl.writeReqs", "dram.writeBursts", "writeReqs")),
        l3_write_misses,
        0.0,
    )
    memory_accesses = memory_reads + memory_writes

    itlb_accesses = _first_non_zero(
        _find_first_stat(root_stats, ("itlb.overallAccesses::total", "itlb.ReadReq_accesses::total")),
        total_instructions,
        0.0,
    )
    itlb_misses = _first_non_zero(
        _find_first_stat(root_stats, ("itlb.overallMisses::total", "itlb.ReadReq_misses::total")),
        0.0,
    )
    dtlb_accesses = _first_non_zero(
        _find_first_stat(root_stats, ("dtlb.overallAccesses::total", "dtlb.ReadReq_accesses::total")),
        load_instructions + store_instructions,
        0.0,
    )
    dtlb_misses = _first_non_zero(
        _find_first_stat(root_stats, ("dtlb.overallMisses::total", "dtlb.ReadReq_misses::total")),
        0.0,
    )

    btb_read_accesses = _first_non_zero(
        _find_first_stat(root_stats, ("BTBLookups",)),
        branch_instructions,
        0.0,
    )
    btb_write_accesses = branch_mispredictions

    noc_total_accesses = _first_non_zero(
        _sum_matching_suffixes(root_stats, ("xbar.pktCount::total",)),
        l2_read_accesses + l2_write_accesses + l3_read_accesses + l3_write_accesses,
        0.0,
    )
    noc_duty_cycle = (
        min(1.0, noc_total_accesses / total_cycles) if total_cycles > 0 else 0.0
    )

    derived_stats = {
        "mcpat.system.total_cycles": total_cycles,
        "mcpat.system.idle_cycles": idle_cycles,
        "mcpat.system.busy_cycles": busy_cycles,
        "mcpat.core.total_instructions": total_instructions,
        "mcpat.core.int_instructions": int_instructions,
        "mcpat.core.fp_instructions": fp_instructions,
        "mcpat.core.branch_instructions": branch_instructions,
        "mcpat.core.branch_mispredictions": branch_mispredictions,
        "mcpat.core.load_instructions": load_instructions,
        "mcpat.core.store_instructions": store_instructions,
        "mcpat.core.committed_instructions": committed_instructions,
        "mcpat.core.committed_int_instructions": committed_int_instructions,
        "mcpat.core.committed_fp_instructions": committed_fp_instructions,
        "mcpat.core.pipeline_duty_cycle": pipeline_duty_cycle,
        "mcpat.core.rob_reads": total_ops,
        "mcpat.core.rob_writes": total_ops,
        "mcpat.core.rename_reads": int_reg_reads,
        "mcpat.core.rename_writes": int_reg_writes,
        "mcpat.core.fp_rename_reads": float_reg_reads,
        "mcpat.core.fp_rename_writes": float_reg_writes,
        "mcpat.core.inst_window_reads": committed_instructions,
        "mcpat.core.inst_window_writes": committed_instructions,
        "mcpat.core.inst_window_wakeup_accesses": committed_instructions * 2.0,
        "mcpat.core.fp_inst_window_reads": fp_instructions,
        "mcpat.core.fp_inst_window_writes": fp_instructions,
        "mcpat.core.fp_inst_window_wakeup_accesses": fp_instructions * 2.0,
        "mcpat.core.int_regfile_reads": int_reg_reads,
        "mcpat.core.float_regfile_reads": float_reg_reads,
        "mcpat.core.int_regfile_writes": int_reg_writes,
        "mcpat.core.float_regfile_writes": float_reg_writes,
        "mcpat.core.function_calls": _find_first_stat(root_stats, ("commitStats0.functionCalls",)),
        "mcpat.core.context_switches": 0.0,
        "mcpat.core.ialu_accesses": ialu_accesses,
        "mcpat.core.fpu_accesses": fpu_accesses,
        "mcpat.core.mul_accesses": mul_accesses,
        "mcpat.core.cdb_alu_accesses": ialu_accesses,
        "mcpat.core.cdb_mul_accesses": mul_accesses,
        "mcpat.core.cdb_fpu_accesses": fpu_accesses,
        "mcpat.core.ifu_duty_cycle": pipeline_duty_cycle,
        "mcpat.core.lsu_duty_cycle": lsu_duty_cycle,
        "mcpat.core.mmu_i_duty_cycle": pipeline_duty_cycle,
        "mcpat.core.mmu_d_duty_cycle": lsu_duty_cycle,
        "mcpat.core.alu_duty_cycle": min(1.0, ialu_accesses / total_cycles) if total_cycles > 0 else 0.0,
        "mcpat.core.mul_duty_cycle": min(1.0, mul_accesses / total_cycles) if total_cycles > 0 else 0.0,
        "mcpat.core.fpu_duty_cycle": min(1.0, fpu_accesses / total_cycles) if total_cycles > 0 else 0.0,
        "mcpat.core.alu_cdb_duty_cycle": min(1.0, ialu_accesses / total_cycles) if total_cycles > 0 else 0.0,
        "mcpat.core.mul_cdb_duty_cycle": min(1.0, mul_accesses / total_cycles) if total_cycles > 0 else 0.0,
        "mcpat.core.fpu_cdb_duty_cycle": min(1.0, fpu_accesses / total_cycles) if total_cycles > 0 else 0.0,
        "mcpat.tlb.itlb.accesses": itlb_accesses,
        "mcpat.tlb.itlb.misses": itlb_misses,
        "mcpat.tlb.dtlb.accesses": dtlb_accesses,
        "mcpat.tlb.dtlb.misses": dtlb_misses,
        "mcpat.cache.l1i.read_accesses": icache_read_accesses,
        "mcpat.cache.l1i.read_misses": icache_read_misses,
        "mcpat.cache.l1d.read_accesses": dcache_read_accesses,
        "mcpat.cache.l1d.write_accesses": dcache_write_accesses,
        "mcpat.cache.l1d.read_misses": dcache_read_misses,
        "mcpat.cache.l1d.write_misses": dcache_write_misses,
        "mcpat.branch.btb.read_accesses": btb_read_accesses,
        "mcpat.branch.btb.write_accesses": btb_write_accesses,
        "mcpat.directory.l1.read_accesses": dcache_read_accesses,
        "mcpat.directory.l1.write_accesses": dcache_write_accesses,
        "mcpat.directory.l1.read_misses": dcache_read_misses,
        "mcpat.directory.l1.write_misses": dcache_write_misses,
        "mcpat.directory.l1.conflicts": 0.0,
        "mcpat.directory.l2.read_accesses": l2_read_accesses,
        "mcpat.directory.l2.write_accesses": l2_write_accesses,
        "mcpat.directory.l2.read_misses": l2_read_misses,
        "mcpat.directory.l2.write_misses": l2_write_misses,
        "mcpat.directory.l2.conflicts": 0.0,
        "mcpat.cache.l2.read_accesses": l2_read_accesses,
        "mcpat.cache.l2.write_accesses": l2_write_accesses,
        "mcpat.cache.l2.read_misses": l2_read_misses,
        "mcpat.cache.l2.write_misses": l2_write_misses,
        "mcpat.cache.l2.conflicts": 0.0,
        "mcpat.cache.l2.duty_cycle": min(1.0, (l2_read_accesses + l2_write_accesses) / total_cycles) if total_cycles > 0 else 0.0,
        "mcpat.cache.l3.read_accesses": l3_read_accesses,
        "mcpat.cache.l3.write_accesses": l3_write_accesses,
        "mcpat.cache.l3.read_misses": l3_read_misses,
        "mcpat.cache.l3.write_misses": l3_write_misses,
        "mcpat.cache.l3.conflicts": 0.0,
        "mcpat.cache.l3.duty_cycle": min(1.0, (l3_read_accesses + l3_write_accesses) / total_cycles) if total_cycles > 0 else 0.0,
        "mcpat.noc.total_accesses": noc_total_accesses,
        "mcpat.noc.duty_cycle": noc_duty_cycle,
        "mcpat.memory.accesses": memory_accesses,
        "mcpat.memory.reads": memory_reads,
        "mcpat.memory.writes": memory_writes,
    }

    root_stats.update({key: _format_stat(value) for key, value in derived_stats.items()})
    return normalized
