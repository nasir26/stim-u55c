# stim-u55c

FPGA-accelerated, [Stim](https://github.com/quantumlib/Stim)-compatible bulk
sampling for stabilizer quantum error-correction circuits, targeting the
Xilinx/AMD Alveo U55C.

**Status: Phase 0 (environment survey + repo skeleton). No kernel code yet.**
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
kernel/       HLS C++ kernel: frame store, gate ops, PRNG, detector fold (Phase 2+)
host/         XRT host runtime: scheduler, instruction encoder, Mode A/B runners (Phase 2+)
python/       Stim-API-compatible Python package (stim_u55c)
softmodel/    Bit-exact Python reference model of the kernel, used in CI without hardware
tests/        Validation harness (Tiers 1-5, see docs/validation.md once written)
bench/        Benchmark scripts and results
docs/         Architecture notes, utilization reports
build/        v++ build flow: Makefile, connectivity.cfg, xrt.ini
```

## Phased plan

Each phase has an explicit acceptance gate; work does not advance to the
next phase, and nothing is pushed, until the current gate is met.

- **Phase 0 — environment survey + skeleton.** *(current)* Repo skeleton,
  LICENSE, NOTICE, CI wired to run against CPU Stim. Gate: CI green, repo
  public, no kernel code.
- **Phase 1 — soft model.** `softmodel/reference_sampler.py` reproduces
  Stim detector samples for a d=3 repetition code and a d=3 surface code.
  Gate: Tier 1 (noiseless determinism), Tier 3 (single-fault vs. DEM), and
  Tier 4 (statistical equivalence) pass in software only.
- **Phase 2 — HLS kernel, sw_emu.** Frame store, gate ops, PRNG, detector
  fold, with per-module C-sim testbenches. Gate: sw_emu bit-exact against
  the soft model (Tier 2) for d=3 and d=5.
- **Phase 3 — hw_emu + synthesis.** II=1 within instruction layers. Gate:
  hw_emu bit-exact, estimated Fmax >= 250 MHz, resource usage under 70% of
  any single class.
- **Phase 4 — hardware bring-up, Mode A (bulk throughput).** Gate: all five
  validation tiers pass on real hardware; shots/sec benchmark vs. CPU Stim
  committed to `bench/results/`.
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
