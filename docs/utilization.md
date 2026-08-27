# Kernel utilization and timing

Numbers below are `vitis_hls` C-synthesis (`csynth_design`) estimates for
`stim_frame_sampler`, not a post-place-and-route Vivado implementation
report — that requires a full `v++` build, which needs `host/`
(Phase 4). Regenerate with:

```
vitis_hls -f kernel/hls/run_hls.tcl
```

from the repo root. Part and clock target live in
`kernel/hls/run_hls.tcl` (`xcu55c-fsvh2892-2L-e`, 300 MHz), not
duplicated here.

## 2026-08-27 — Phase 3 baseline

| | |
|---|---|
| Vitis HLS | 2023.2 |
| Target clock | 3.33 ns (300 MHz) |
| Estimated clock | 2.615 ns |
| **Estimated Fmax** | **382.44 MHz** |
| Loop constraints | all satisfied |

Resource utilization, against one SLR (the binding constraint — the
kernel isn't yet partitioned across the part's 3 SLRs) and against the
whole part:

| Resource | Used | SLR budget | SLR % | Part budget | Part % |
|---|---:|---:|---:|---:|---:|
| LUT | 217,052 | 434,560 | 49% | 1,303,680 | 16% |
| FF | 174,517 | 869,120 | 20% | 2,607,360 | 6% |
| DSP | 960 | 3,008 | 31% | 9,024 | 10% |
| BRAM_18K | 66 | 1,344 | 4% | 4,032 | 1% |
| URAM | 0 | 320 | 0% | 960 | 0% |

Both Fmax and every resource class clear the Phase 3 gate (>= 250 MHz,
< 70% of any single class) — with the numbers above the SLR-relative
figures, the tighter of the two ways to read the gate.

**One real finding from this run, not from review:** the first synthesis
attempt put SLR-relative LUT at 83% — over the gate. `draw_flip_mask`
(used by X/Y/Z noise) and `draw_categorical` (used by DEPOLARIZE1/2) were
two separate C++ functions, each fully unrolling its own 64-lane,
10-round Philox4x32 bank; being textually different functions gave HLS
no basis to share hardware between them even though the noise opcodes
that call them are mutually exclusive within one instruction. Merging
them into a single `draw_noise` (kernel/stim_frame_sampler.cpp) let HLS's
ordinary mutually-exclusive-branch resource sharing consolidate the two
banks into one: DSP dropped 1920 -> 960, LUT 361,185 -> 217,052, SLR LUT
83% -> 49%, with the numbers in the table above being the result. No
change to the frame/gate/detector-fold logic these numbers describe.

**C/RTL cosimulation: PASS.** `vitis_hls`'s `cosim_design` runs the actual
synthesized RTL (via XSIM) against the same C testbench used for Tier 2
(`kernel/hls_testbench/tb_stim_frame_sampler.cpp`, fed
`kernel/hls/test_vectors/instructions.bin` — regenerate with
`kernel/hls/generate_test_vector.py`) and checks RTL and C-level behavior
agree bit-for-bit. It does; independently re-checking the RTL's actual
output file against `softmodel/kernel_replay.py` (not just trusting
cosim's own PASS verdict) confirms the same thing: detector and
observable words match exactly. Chained with Tier 2 (C-sim matches the
soft model), this means soft model == C-sim == synthesized RTL,
transitively — as close to "hw_emu bit-exact" as achievable without a
full `v++ -t hw_emu` build, which needs `host/` (XRT buffers, AXI/HBM DMA
simulation) and doesn't exist until Phase 4. Reproduce with
`make hls-cosim` (`build/Makefile`).

## 2026-08-27 — instruction layering: implemented, verified, not yet exploited

Project brief section 3.1's "hard problem" -- partition the instruction
stream into layers of mutually qubit-disjoint instructions -- is now
implemented (`kernel/isa.py:_layer_and_reorder`), runs as the last step
of `encode_circuit`, and is verified: a Python-side check that no two
instructions in the same layer share a qubit passes for all three test
circuits, and `tests/test_kernel_tier2.py` confirms the reorder is
bit-exact (reordering only ever changes each instruction's own PRNG
counter value, never which qubit sees which effect in what relative
order -- see that function's docstring for the full argument). Average
instructions per layer, for the same circuits Phase 1/2 used:

| Circuit | Instructions | Layers | Avg instrs/layer |
|---|---:|---:|---:|
| repetition_code d3 | 45 | 14 | 3.2 |
| surface_code d3 | 344 | 47 | 7.3 |
| surface_code d5 | 1,674 | 77 | 21.7 |

(d=11/d=21, which the project brief also asks for here, need
`NUM_QUBITS_MAX` raised past its current 128 -- d=11 alone needs 274
qubits. That's a config change, not a redesign, but wasn't done this
pass since it wasn't needed for the d=3/d=5 target this phase has been
scoped to.) Parallelism improves with qubit count, as expected -- more
qubits means more mutually-disjoint work available per layer.

The kernel's top-level signature now takes `layer_offsets`/`num_layers`
and processes instructions in a `LAYER_LOOP` / `INSTRUCTION_LOOP` nest
matching that structure, but **the inner loop is not pipelined** in the
version this repository ships. That was tried, measured, and reverted:

**The experiment.** `#pragma HLS pipeline II=1` plus
`#pragma HLS dependence variable=fs.x/fs.z inter false` on
`INSTRUCTION_LOOP` (the dependence override is sound -- it's exactly the
frame-store guarantee layering provides). Result: HLS could only reach
**II=34**, not 1, and reaching even that pushed SLR-relative LUT usage to
**131%** -- over the 70% gate -- while Fmax *dropped* slightly (382.44 ->
351.25 MHz). A worse design on every axis that mattered for this phase's
gate, despite being a genuine attempt at the thing the gate asks for.
Per the project's own working rule ("if a fix requires an architectural
change, stop and explain the tradeoff rather than working around it"),
this was reverted rather than adopted or quietly left over-budget.

**Why II=34, not 1 -- two causes, both reported by HLS itself, not
guessed at:**
1. The detector/observable accumulators in `DetectorFold` are a real
   read-modify-write hazard layering-by-qubit doesn't touch: two
   qubit-disjoint measurements in the same layer can still both
   contribute to the *same* detector (common -- several ancillas' results
   often feed one detector), so consecutive fold() calls can have a
   genuine loop-carried dependency on the same accumulator words. HLS's
   own dependence checker correctly refused to pipeline through this
   (`HLS 200-880`, citing `detector_fold.hpp:47`) -- overriding it would
   have been unsound, not just conservative, so it wasn't.
2. `instructions` is fetched from external memory (m_axi) once per loop
   iteration, and `Instruction`'s 32-byte `detector_mask` means each
   fetch is several separate AXI transactions -- HLS reported this as its
   own, independent II-limiting factor (`HLS 200-885`, "limited memory
   ports").

Fixing (1) needs a different detector-fold structure (e.g. splitting
accumulators so same-layer measurements can't collide, or deferring the
fold to a separate pass); fixing (2) needs the instruction stream staged
on-chip (BRAM/URAM) rather than re-fetched from external memory every
iteration, or a narrower per-iteration record. Both are real, scoped
follow-up work, not attempted here.

**What shipped instead:** the layering algorithm, the layer-aware kernel
API, and the `LAYER_LOOP`/`INSTRUCTION_LOOP` structure, all with zero
pipelining directives on the inner loop -- functionally and resource-wise
equivalent to the pre-layering baseline above (Fmax unchanged at 382.44
MHz; SLR LUT 50% vs. the baseline's 49%, FF 18% vs 20%, DSP 23% vs 31%,
the small deltas being the extra loop nesting and the now-unused
`layer_offsets` array, not pipelining cost). Nothing here makes the
kernel faster yet, but the layering computation itself is done, correct,
and ready for whoever picks up the pipelining problem with (1) and (2)
solved first.
