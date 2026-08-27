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

**Not yet done:** `INSTRUCTION_LOOP` (the main per-instruction loop) is
not pipelined -- iteration latency is 75-496 cycles depending on opcode,
dominated by the 64-lane Philox draw on noise instructions. This is the
"II=1 within layers" half of Phase 3's gate (project brief section 3.1):
it needs a host-side scheduler that partitions the instruction stream
into layers of mutually qubit-disjoint instructions, plus a kernel-side
restructuring to pipeline within a layer and drain between them. The
kernel is functionally correct regardless (a same-qubit hazard just costs
cycles, not correctness), which is what let Phase 2's gate and this
synthesis run proceed without it, but the gate as stated in the phased
plan isn't fully met until that scheduler exists.
