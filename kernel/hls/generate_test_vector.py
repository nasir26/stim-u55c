#!/usr/bin/env python3
"""Regenerates kernel/hls/test_vectors/instructions.bin, the fixed input
run_hls.tcl's cosim step (STIM_U55C_HLS_COSIM=1) points cosim_design's
-argv at. Not committed (see .gitignore) since it's fully reproducible
from this script; run it before a cosim run if the file is missing.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "python"))
sys.path.insert(0, str(_REPO_ROOT / "kernel"))

import stim  # noqa: E402
from isa import encode_circuit  # noqa: E402


def main() -> None:
    circuit = stim.Circuit.generated(
        "repetition_code:memory", rounds=3, distance=3,
        before_round_data_depolarization=0.05, before_measure_flip_probability=0.05,
    )
    program = encode_circuit(circuit)
    out_dir = Path(__file__).resolve().parent / "test_vectors"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "instructions.bin").write_bytes(program.serialize())
    print(f"wrote {out_dir / 'instructions.bin'}: {len(program.instructions)} instructions, "
          f"{program.num_detectors} detectors")


if __name__ == "__main__":
    main()
