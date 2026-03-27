import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


MCPAT_ROOT = Path(__file__).resolve().parents[1]
if str(MCPAT_ROOT) not in sys.path:
    sys.path.insert(0, str(MCPAT_ROOT))

from pypat.conversion.gem5_to_mcpat import run_conversion  # noqa: E402
from pypat.conversion.profiles import normalize_gem5_config  # noqa: E402


def _component(tree: ET.ElementTree, component_id: str) -> ET.Element:
    element = tree.find(f".//component[@id='{component_id}']")
    assert element is not None
    return element


def _named_value(
    tree: ET.ElementTree, component_id: str, tag: str, name: str
) -> str:
    component = _component(tree, component_id)
    element = component.find(f"./{tag}[@name='{name}']")
    assert element is not None
    return element.attrib["value"]


def test_normalize_gem5_config_builds_kunpeng_mcpat_model():
    config = {
        "system": {"isa": "ArmISA"},
        "board": {
            "clk_freq": "2.6GHz",
            "processor": {"num_cores": 64},
            "cache_hierarchy": {
                "l1i_size": "64KiB",
                "l1d_size": "64KiB",
                "l2_size": "512KiB",
                "l3_size": "64MiB",
            },
            "memory": {"num_channels": 8},
        },
    }

    normalized, selected = normalize_gem5_config(config, "arm64-kunpeng920")
    profile = normalized["profile"]
    mcpat = normalized["mcpat"]

    assert selected == "arm64-kunpeng920"
    assert profile["number_of_cores"] == 64
    assert profile["number_of_l2s"] == 64
    assert profile["number_of_l3s"] == 16
    assert profile["number_of_nocs"] == 2
    assert profile["l3_size"] == 4 * 1024 * 1024
    assert profile["memory_channels_per_mc"] == 4
    assert mcpat["system"]["clusters"] == 16
    assert mcpat["caches"]["l3"]["total_size_bytes"] == 64 * 1024 * 1024


def test_run_conversion_emits_derived_kunpeng_stats(tmp_path):
    target_dir = tmp_path / "kunpeng_conversion"
    target_dir.mkdir()

    config = {
        "system": {
            "isa": "ArmISA",
            "processor": {"o3": {"0": {"core": {"numThreads": 1}}}},
        },
        "board": {
            "clk_freq": "2.6GHz",
            "cache_hierarchy": {
                "l1i_size": "64KiB",
                "l1d_size": "64KiB",
                "l2_size": "512KiB",
                "l3_size": "64MiB",
            },
            "processor": {"num_cores": 64},
            "memory": {"num_channels": 8},
        },
    }
    stats = "\n".join(
        [
            "simTicks 2600000",
            "simInsts 4000",
            "system.cpu.commitStats0.numIntInsts 2500",
            "system.cpu.commitStats0.numFpInsts 500",
            "system.cpu.commitStats0.numVecInsts 300",
            "system.cpu.commitStats0.numLoadInsts 700",
            "system.cpu.commitStats0.numStoreInsts 300",
            "system.cpu.commitStats0.functionCalls 12",
            "system.cpu.fetchStats0.numBranches 250",
            "system.cpu.branchPred.condIncorrect 5",
            "system.cpu.branchPred.BTBLookups 250",
            "system.cpu.executeStats0.numIntRegReads 5000",
            "system.cpu.executeStats0.numIntRegWrites 2500",
            "system.cpu.executeStats0.numFpRegReads 1000",
            "system.cpu.executeStats0.numFpRegWrites 500",
            "system.cpu.executeStats0.numVecRegReads 600",
            "system.cpu.executeStats0.numVecRegWrites 300",
            "system.cpu.executeStats0.numIntAluAccesses 2600",
            "system.cpu.executeStats0.numFpAluAccesses 600",
            "system.cpu.executeStats0.numVecAluAccesses 400",
            "system.cpu.icache.ReadReq_accesses::total 4200",
            "system.cpu.icache.ReadReq_misses::total 42",
            "system.cpu.dcache.ReadReq_accesses::total 700",
            "system.cpu.dcache.WriteReq_accesses::total 300",
            "system.cpu.dcache.ReadReq_misses::total 70",
            "system.cpu.dcache.WriteReq_misses::total 30",
            "system.l2.ReadReq_accesses::total 100",
            "system.l2.WriteReq_accesses::total 40",
            "system.l2.ReadReq_misses::total 10",
            "system.l2.WriteReq_misses::total 4",
            "system.l3.ReadReq_accesses::total 20",
            "system.l3.WriteReq_accesses::total 8",
            "system.l3.ReadReq_misses::total 2",
            "system.l3.WriteReq_misses::total 1",
            "system.mem_ctrl.readReqs 2",
            "system.mem_ctrl.writeReqs 1",
            "---------- End Simulation Statistics ----------",
            "",
        ]
    )

    (target_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
    (target_dir / "stats.txt").write_text(stats, encoding="utf-8")
    outfile = target_dir / "conv.xml"

    selected = run_conversion(
        stats_file=target_dir / "stats.txt",
        config_file=target_dir / "config.json",
        outfile=outfile,
        template_profile="arm64-kunpeng920",
    )

    assert selected == "arm64-kunpeng920"
    tree = ET.parse(outfile)

    assert _named_value(tree, "system", "param", "number_of_cores") == "64"
    assert _named_value(tree, "system", "param", "number_of_L3s") == "16"
    assert _named_value(tree, "system.core0", "stat", "total_instructions") == "4000"
    assert _named_value(tree, "system.core0", "stat", "fp_instructions") == "800"
    assert _named_value(tree, "system.core0.dcache", "stat", "write_accesses") == "300"
    assert _named_value(tree, "system.L30", "stat", "read_misses") == "2"
