# kernel/

HLS C++ kernel sources and the ISA that drives them.

- `isa.py` / `generate_headers.py` — single source of truth for opcode
  numbering and sizing constants; generates `opcodes.hpp`, `config.hpp`,
  `depolarize2_table.hpp`. Run `python3 kernel/generate_headers.py` after
  editing `isa.py` or `python/stim_u55c/config.py` (CI checks staleness —
  `tests/test_generated_headers_up_to_date.py`).
- `frame_store.hpp` — URAM-resident, shot-axis-partitioned Pauli frame.
- `gate_ops.hpp` — every Clifford gate as a read-XOR-write.
- `prng.hpp` — Philox4x32-10, counter-based, bit-identical to
  `softmodel/philox.py`.
- `detector_fold.hpp` — measurement → detection-event reduction, folded
  compile-time (no runtime measurement-history buffer needed — see its
  docstring).
- `instruction.hpp` — the in-memory instruction record and binary reader.
- `stim_frame_sampler.cpp` / `.hpp` — the top-level kernel function.
- `ap_uint_shim.hpp` — portable `ap_uint<N>` stand-in so all of the above
  compiles with plain g++ (no Vitis install needed) for Tier 1/2 CI; swap
  for real `<ap_int.h>` when Phase 3 needs actual HLS synthesis.
- `hls_testbench/` — one C-sim testbench per module, plus the end-to-end
  Tier 2 comparison (`tb_stim_frame_sampler.cpp`).

Layered/hazard-free instruction scheduling for II=1 (the project brief's
section 3.1) is a Phase 3 concern: the kernel loop here is functionally
correct regardless of instruction order (HLS just inserts stalls on a
same-qubit hazard rather than corrupt anything), which is what Phase 2's
gate — sw_emu-equivalent output bit-exact against the soft model — needs.
