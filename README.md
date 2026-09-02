# stim-u55c

FPGA-accelerated, [Stim](https://github.com/quantumlib/Stim)-compatible bulk
sampling for stabilizer quantum error-correction circuits, targeting the
Xilinx/AMD Alveo U55C.

**Status: Phase 3 gate met on HLS estimates (Fmax 382 MHz, all resource
classes under 70%, RTL cosimulation bit-exact). Phase 4: timing closed on
the fifth real `hw` build (~24 hours of cumulative Vivado build time,
WNS 0.000ns — see docs/utilization.md) and run on the physical Alveo
U55C. All five validation tiers now pass on real hardware, not just in
software or emulation: Tier 1 (noiseless, all detectors zero), Tier 2
(bit-exact vs. the soft model, 3 circuits), Tier 3 (458/458 DEM error
mechanisms), Tier 4 (10,000,000 shots/circuit, max\|z\| 2.91 against a 5σ
bar), Tier 5 (logical error rate via PyMatching, surface code d=3/d=5,
max\|z\| 1.59) — see bench/results/2026-09-01-hardware-validation.md.
d=7/9/11 for Tier 5 need a larger `NUM_QUBITS_MAX` and a new `hw` build,
not yet attempted. Mode A shots/sec benchmark against CPU Stim is
committed and honest: CPU Stim is currently 5.6x-15.3x faster on these
circuits, for two already-known, already-documented reasons (unpipelined
instruction loop, small SHOTS=64 batch) — see
bench/results/2026-09-01-mode-a-throughput.md.**
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
paper/        Submittable research paper (Journal of Supercomputing), Overleaf-ready
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
  `docs/utilization.md`. **`hw` closed timing on the fifth attempt
  (~24 hours of cumulative Vivado build time) and ran on the physical
  card.** Five real synthesis+implementation runs against
  `xcu55c-fsvh2892-2L-e`, confirming the project brief's "hours long"
  warning every time (3-5.5 hours each). Post-route resource usage was
  excellent and consistent throughout, ~2.6x *better* than HLS's own
  `csynth` estimate (~7% LUT of the kernel's fabric budget vs. the
  217,052-LUT estimate Phase 3 reported) — a reminder that an HLS
  estimate is a conservative upper bound, not a stand-in for what real
  technology mapping produces. Timing: attempt 1 (300 MHz) WNS -0.688ns;
  attempt 2's "250 MHz" retarget didn't actually apply (`--kernel_frequency`
  needed on both `v++ -c` and `-l`, only had it on one) — caught by
  checking the routed report's actual clock period, not trusting the
  intended change; attempt 3, fix applied for real, WNS -0.179ns;
  attempt 4, `AggressiveExplore` placement/routing/post-route-physopt
  directives targeted at the recurring Philox bottleneck, WNS -0.041ns;
  attempt 5, `route_design` switched to `NoTimingRelaxation`: **WNS
  0.000ns, zero failing endpoints** — "All user specified timing
  constraints are met." With timing genuinely closed, `./run_and_validate.sh
  hw` was run against the physical Alveo U55C: **bit-exact PASS** against
  `softmodel/kernel_replay.py` for all three Tier 2 circuits (repetition
  code d=3, surface code d=3 and d=5). Soft model == C-sim == HLS RTL
  cosimulation == `sw_emu` == `hw_emu` == **real silicon** — the full
  chain this project set out to validate. Full account of all five
  attempts, including every failing path along the way, in
  `docs/utilization.md`.
  **All five validation tiers pass on real hardware.** With a working
  `xrt_runner`, extending to Tiers 1/3/4 turned out to be mostly
  composition, not new engineering: Tier 1 (noiseless, stripped circuits
  through the same kernel — all detector/observable words exactly zero,
  all 64 shot lanes, 3 circuits); Tier 3 (`softmodel/reference_sampler.py:build_single_fault_circuit`
  turns a DEM error's location into an actual forced-fault `stim.Circuit`,
  cross-checked against the already-validated interpreter-based
  `sample_single_fault` before trusting it on hardware time — 458/458 DEM
  mechanisms **PASS**, ~92s); Tier 4 (`host/xrt_tier4.cpp`, double-buffered
  like the benchmark below but accumulating per-detector fired-counts
  instead of discarding output — 10,000,000 shots/circuit against CPU
  Stim, max\|z\| 1.64 / 2.91 / 2.64, **PASS**, ~6m 42s total).

  **Tier 5** (`host/xrt_tier5.cpp`, `bench/hw_tier5.py`) needed one more
  piece of real engineering: the kernel's output is detector-major, but
  PyMatching's `decode_batch` wants shot-major bit-packed syndromes
  (Stim's own b8 convention) — transposed on the host per batch, cheap
  next to the kernel launch itself, and cross-checked against the
  independently-validated Tier 4 tool's aggregate counts before trusting
  it. Surface code d=3 and d=5 (the distances `NUM_QUBITS_MAX=128`
  covers), 3 physical error rates each, decoded with the identical
  PyMatching matcher on both the FPGA's real syndromes and CPU-Stim's:
  **PASS**, max\|z\| 1.59, ~2m 21s total — and the logical error rates
  themselves show the right qualitative behavior (d=5 beats d=3 below
  the apparent threshold, loses above it) without that being targeted.
  d = 7, 9, 11 not attempted — d=7 alone needs more qubits than
  `NUM_QUBITS_MAX = 128` supports, so reaching them needs a config change
  and a fresh, likely multi-attempt timing closure (per the five-attempt,
  ~24-hour experience closing timing at the *current*, smaller design) —
  real, scoped, separate work.

  Full account of all five tiers in
  `bench/results/2026-09-01-hardware-validation.md` and
  `bench/results/2026-09-02-tier5-logical-error-rate.md`.

  The **shots/sec benchmark** (`host/xrt_bench.cpp`, `bench/run_benchmark.py`)
  needed real engineering, not composition: a naive one-process-per-shot-batch
  approach (`xrt_runner`) reloads the `.xclbin` every call, which dominates
  runtime completely, so the benchmark tool loads the device once and
  pipelines 2 `xrt::run` objects in flight (per the project brief's own
  Mode A description) so host-side setup for run *i+1* overlaps run *i*'s
  execution. Result, honestly reported: **CPU Stim is currently faster**
  than this kernel on these circuits — 5.6x (repetition d=3) to 15.3x
  (surface d=5). Two already-known, already-documented reasons, not new
  findings: `INSTRUCTION_LOOP` is unpipelined (Phase 3's reverted II=1
  attempt), and `SHOTS=64` is a small batch chosen for Phase 2
  convenience, not throughput (`python/stim_u55c/config.py` already says
  so). Full methodology and numbers in
  `bench/results/2026-09-01-mode-a-throughput.md`.

  Gate: all five validation tiers pass on real hardware (**done**);
  shots/sec benchmark vs. CPU Stim committed to `bench/results/`
  (**done**, honestly — CPU currently wins). d=7/9/11 for Tier 5 remain
  open, needing the `NUM_QUBITS_MAX`/rebuild work described above.
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
