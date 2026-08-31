# stim-u55c

FPGA-accelerated, [Stim](https://github.com/quantumlib/Stim)-compatible bulk
sampling for stabilizer quantum error-correction circuits, targeting the
Xilinx/AMD Alveo U55C.

**Status: Phase 3 gate met on HLS estimates (Fmax 382 MHz, all resource
classes under 70%, RTL cosimulation bit-exact); instruction layering
implemented and verified, pipelining it (II=1) tried, measured
over-budget, and reverted. Phase 4: `sw_emu` and `hw_emu` both pass
end-to-end through the real XRT stack, bit-exact against the soft model.
Three real `hw` builds attempted (~10 hours total): resource usage is
excellent and consistent throughout (~7% LUT, ~2.6x better than the HLS
estimate); timing has not closed, improving from WNS -0.688ns (300 MHz
target) to -0.179ns once a `--kernel_frequency` build-script bug was
found and fixed (250 MHz genuinely applied, not just requested) — close,
but not there, with all three attempts pointing at the same Philox
noise-generator logic as the recurring bottleneck. Not run on physical
hardware. See docs/utilization.md for the full, honest account.**
See [Phased plan](#phased-plan) below for what that means concretely.

## What this is, and is not

This project accelerates one specific, well-isolated part of stabilizer
circuit simulation: **Pauli frame propagation and detector sampling**
(Sections 3 and 5.6 of Gidney, *Stim: a fast stabilizer circuit simulator*,
Quantum 5, 497 (2021)). It does **not** reimplement Stim's tableau simulator
(Section 4), and it does **not** reimplement a matching decoder — both of
those stay on the CPU, using upstream [Stim](https://github.com/quantumlib/Stim)
and [PyMatching 2](https://github.com/oscarhiggott/PyMatching) unmodified.

The reasoning, briefly:

- **Tableau simulation (Stim §4)** is control-flow heavy: data-dependent
  Gaussian elimination over rows and an in-place row/column transpose to
  switch access patterns. All of that is hostile to HLS pipelining. It has
  no business on an FPGA and stays on the CPU.
- **Pauli frame simulation (Stim §3)** is pure XOR/AND over bit vectors,
  embarrassingly parallel across independent shots, and has no floating
  point. Gidney's vectorized CNOT (§3, Fig. 3) is two XORs per gate per
  lane. This is the FPGA target.
- **Detector sampling (Stim §5.6)** folds naturally into the same kernel:
  fold the measurement-XOR reduction into detection events on-chip so only
  detector bits cross PCIe, not raw measurement bits.
- Stim §5.3 documents a **GPU failure**, not a GPU implementation: Gidney
  benchmarked a WebGL2 XOR shader and found it roughly CPU-speed, because
  the workload's arithmetic intensity is too low to favor a GPU's compute
  throughput. That is exactly the regime where on-chip URAM plus
  wide, fixed wiring (an FPGA) should win instead — this project is a test
  of that hypothesis, not an assumption of it.

The pipeline is:

```
CPU (upstream Stim)                    FPGA (this kernel)                CPU (PyMatching 2)
--------------------                   -------------------               ------------------
parse circuit                          batched Pauli frame propagation
tableau sim -> reference sample  --->  reference XOR + detector fold --->  sparse blossom decode
detector error model (DEM)             bit-packed detector output          logical error rate
```

## Repository layout

```
kernel/       HLS C++ kernel + ISA: frame store, gate ops, PRNG, detector fold, isa.py
host/         XRT host runtime: xrt_runner.cpp (Mode A); Mode B is Phase 5
python/       Stim-API-compatible Python package (stim_u55c), incl. config.py
softmodel/    Bit-exact Python reference model of the kernel, used in CI without hardware
tests/        Validation harness (Tiers 1-5, see "Validation strategy" below)
bench/        Benchmark scripts and results
docs/         Architecture notes, utilization reports
build/        v++ build flow: Makefile, connectivity.cfg, xrt.ini
```

## Phased plan

Each phase has an explicit acceptance gate; work does not advance to the
next phase, and nothing is pushed, until the current gate is met.

- **Phase 0 — environment survey + skeleton.** *(done)* Repo skeleton,
  LICENSE, NOTICE, CI wired to run against CPU Stim. Gate: CI green, repo
  public, no kernel code.
- **Phase 1 — soft model.** *(done, current)* `softmodel/reference_sampler.py`
  is a from-scratch Pauli frame interpreter over `stim.Circuit` (recursing
  into REPEAT blocks rather than flattening them, so single-fault
  injection can locate an exact instruction occurrence -- see its
  docstring). Reproduces Stim detector samples for a d=3 repetition code
  and a d=3 surface code (both memory bases). Gate: Tier 1 (noiseless
  determinism), Tier 3 (440 DEM error mechanisms across both circuits,
  every one matched exactly), and Tier 4 (10^7 shots per circuit vs. CPU
  Stim, max |z| observed 2.6 against a 5-sigma bar) all pass in software
  only -- see `tests/test_softmodel_validation.py`.
- **Phase 2 — HLS kernel, sw_emu.** *(done)* `kernel/isa.py` compiles a
  `stim.Circuit` to a flat instruction stream, un-broadcasting gates and
  resolving all detector/observable folding at compile time (no runtime
  measurement-history buffer -- see `detector_fold.hpp`'s docstring).
  The kernel (`frame_store.hpp`, `gate_ops.hpp`, `prng.hpp` — Philox4x32-10,
  `detector_fold.hpp`, `stim_frame_sampler.cpp`) compiles under plain g++
  via a portable `ap_uint<N>` shim (`ap_uint_shim.hpp`), so this is CI,
  not just local. Gate: C-sim output bit-exact against the soft model
  (Tier 2) for a d=3 repetition code and d=3/d=5 surface codes — see
  `tests/test_kernel_tier2.py`. One real bug caught in the process: a
  hand-transcribed DEPOLARIZE2 combination table silently disagreed with
  the Python side's actual enumeration order; both are now generated from
  one Python list (`kernel/generate_headers.py`) so that class of bug is
  ruled out rather than re-reviewed. "sw_emu" here means this C-sim, not
  an actual `v++ -t sw_emu` run — that needs `host/`, which is Phase 4.
- **Phase 3 — hw_emu + synthesis.** *(gate met)* Real `vitis_hls`
  C-synthesis of the kernel: estimated Fmax 382.44 MHz (target 300, floor
  250), all resource classes under 70% even at the tighter SLR-relative
  reading (LUT 49%, DSP 31%, FF 20%, BRAM 4%, URAM 0%) — see
  `docs/utilization.md`. C/RTL cosimulation (`cosim_design`, real XSIM
  RTL simulation) **passes**, independently re-checked against the soft
  model rather than just trusted: the synthesized RTL's actual output is
  bit-identical to `softmodel/kernel_replay.py`, which chains with Tier 2
  (C-sim matches the soft model) into soft model == C-sim == synthesized
  RTL. One real finding en route: the first synthesis pass put SLR LUT at
  83% (over budget) because two noise-drawing functions each fully
  unrolled their own 64-lane Philox bank with no hardware shared between
  them; merging them into one function let HLS's normal
  mutually-exclusive-branch sharing consolidate it (DSP 1920 -> 960, LUT
  361,185 -> 217,052) — see `docs/utilization.md` for the full account.
  **Instruction layering** (project brief section 3.1's "hard problem")
  is implemented and verified: `kernel/isa.py` partitions the compiled
  stream into layers of mutually qubit-disjoint instructions (avg. 3.2 /
  7.3 / 21.7 instructions per layer for the rep-code/d3/d5 test
  circuits), and the kernel now takes `layer_offsets` and processes a
  matching `LAYER_LOOP`/`INSTRUCTION_LOOP` nest. **Pipelining it wasn't
  adopted:** `#pragma HLS pipeline II=1` (sound here, given the layering
  guarantee) only reached II=34 in practice, bottlenecked by two things
  layering-by-qubit doesn't fix — a real hazard on the detector-fold
  accumulators, and per-instruction external-memory fetch cost — and
  getting even that far pushed SLR LUT usage to 131% (over the 70% gate)
  while *lowering* Fmax. Measured, not guessed at, and reverted per the
  project's own rule about not working around a gate that needs an
  architectural fix — see `docs/utilization.md` for the full account and
  what solving the two root causes would take. Resource/Fmax numbers
  above are for the current (layered-but-unpipelined) kernel, unchanged
  from the pre-layering baseline.
- **Phase 4 — hardware bring-up, Mode A (bulk throughput).** *(underway)*
  `host/xrt_runner.cpp` (real XRT C++ API: device, kernel, buffers, run),
  `build/generate_connectivity.py` (generated `connectivity.cfg`, 4 of the
  U55C's 32 HBM pseudo-channels), `build/vpp_build.sh` +
  `run_and_validate.sh`. **`sw_emu` confirmed working end-to-end**: real
  `v++`-built `.xclbin`, run through the real XRT host runtime, bit-exact
  against `softmodel/kernel_replay.py` — see `build/README.md` for the
  two real bugs (a linker flag order mistake, and `stim_frame_sampler`
  needing `extern "C"` linkage for sw_emu's dlsym-based kernel lookup,
  not just the global scope cosimulation alone required) this surfaced.
  **`hw_emu` also confirmed working**, and it's the more meaningful of
  the two: real synthesized kernel RTL, simulated (XSIM) inside the
  platform's actual PCIe/XDMA/HBM shell, driven by the same XRT host
  code — bit-exact on the first attempt, ~9 minutes of `v++` compile/link
  plus 16 seconds of actual simulated time. Full numbers in
  `docs/utilization.md`. **`hw` attempted three times (~10 hours total),
  timing not yet closed.** Real Vivado synthesis+implementation against
  `xcu55c-fsvh2892-2L-e`, each run ~3-4 hours, confirming the project
  brief's "hours long" warning exactly every time. Post-route resource
  usage is excellent throughout and consistently ~2.6x *better* than
  HLS's own `csynth` estimate (~7% LUT of the kernel's fabric budget vs.
  the 217,052-LUT estimate Phase 3 reported) — a reminder that an HLS
  estimate is a conservative upper bound, not a stand-in for what real
  technology mapping produces. Timing: attempt 1 (300 MHz) missed by WNS
  -0.688ns (~249 MHz achievable); attempt 2 tried retargeting to 250 MHz
  but the fix didn't actually apply (a `--kernel_frequency` flag needed
  on both `v++ -c` and `-l`, only had it on one) — confirmed by checking
  the routed report's actual clock period, not just trusting the
  intended change; attempt 3, with the fix genuinely applied, cut the
  violation to WNS -0.179ns (~239 MHz achievable) — real progress, still
  short. All three runs' failing paths point at the same region: the
  Philox noise-generator logic (`draw_noise`), heavily replicated across
  64 shot lanes. Not run on physical hardware — an unclosed-timing
  bitstream isn't a meaningful correctness check. Full account of all
  three attempts, including each failing path, in `docs/utilization.md`.
  Gate: all five validation tiers pass on real hardware; shots/sec
  benchmark vs. CPU Stim committed to `bench/results/` — both still open,
  pending a build that actually closes timing.
- **Phase 5 — Mode B (low-latency), sinter backend, docs.**

## Validation strategy

A sampler that is fast and subtly wrong is worse than useless. Five tiers,
each gating the next:

1. **Noiseless determinism** — every detector reads zero with all noise
   channels off.
2. **Bit-exact vs. soft model** — identical PRNG seeds must produce
   identical output, kernel vs. `softmodel/reference_sampler.py`. This is
   the tier that runs in CI without hardware.
3. **Single-fault injection vs. DEM** — every mechanism in
   `circuit.detector_error_model(decompose_errors=True)` must fire exactly
   the detector set the DEM predicts.
4. **Statistical equivalence with Stim** — per-detector firing rates and
   pairwise correlations over >= 10^7 shots, checked against CPU Stim.
5. **End-to-end logical error rate** — FPGA detector output through
   PyMatching 2 must reproduce Stim's logical error rate curves across
   d = 3, 5, 7, 9, 11.

## Environment (as surveyed for Phase 0, on the current build machine)

| | |
|---|---|
| Board | Alveo U55C (`xilinx_u55c_gen3x16_xdma_base_3`) |
| Part | `xcu55c-fsvh2892-2L-e`, 3 SLRs |
| XRT | 2.15.225 (branch 2023.1) |
| Vitis / v++ | 2023.2 |
| Platform | `xilinx_u55c_gen3x16_xdma_3_202210_1` |
| Stim (Python) | 1.13.0 |
| PyMatching | 2.4.0 |

Fabric and HBM/URAM/BRAM/DSP counts, and the achieved kernel clock, will be
reported in `docs/utilization.md` once there is a kernel to synthesize
(Phase 3+) — quoting resource numbers before that would just be guessing.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE). This is an
independent reimplementation of published algorithms (see NOTICE for exact
attribution) — no source from Stim or PyMatching is vendored into this repo.
