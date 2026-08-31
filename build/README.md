# build/

v++ build flow.

- `Makefile` — `test` (pytest, real since Phase 0); `hls-synth`/
  `hls-cosim` (Phase 3, `vitis_hls` C-synthesis/cosimulation, local-only);
  `sw_emu`/`hw_emu`/`hw` (real v++ builds via `vpp_build.sh`, local-only,
  never run `hw` casually — see below); `connectivity` (regenerates
  `connectivity.cfg`); `clean`.
- `generate_connectivity.py` — single source of truth for HBM bank
  assignment; generates `connectivity.cfg`. Per the project brief this is
  generated, not handwritten, so bank counts stay one variable to tune.
- `vpp_build.sh <sw_emu|hw_emu|hw>` — `v++ -c`/`-l` (kernel -> .xo ->
  .xclbin), host runtime build, `emconfig.json`. Needs Vitis/XRT sourced.
- `run_and_validate.sh <sw_emu|hw_emu|hw>` — runs a build's `xrt_runner`
  against the fixed test vector `kernel/hls/` cosimulation also uses, and
  diffs the result against `softmodel/kernel_replay.py` bit-for-bit —
  same comparison Tier 2 makes for the C-sim build, now checked through
  the real v++/XRT stack.
- `xrt.ini` — minimal runtime logging config; no profiling by default.

**sw_emu and hw_emu are both confirmed working**: `make <mode> &&
./run_and_validate.sh <mode>` builds and runs end-to-end, bit-exact
against the soft model, through the real XRT host runtime — not just
C-sim or HLS cosimulation. `hw_emu` is the more meaningful of the two: it
simulates the actual synthesized kernel RTL inside the platform's real
PCIe/XDMA/HBM shell (XSIM), not an approximation of the kernel the way
sw_emu's functional simulation is — the closest validation to real
hardware short of the physical card, and it passed first try (~9 minutes
of `v++` compile/link, 16 seconds of actual simulated time). Full numbers
in `../docs/utilization.md`.

Two real bugs getting sw_emu working, neither in the kernel logic itself
(hw_emu needed no further fixes once these were in place):
1. `vpp_build.sh`'s host-compile line had `-lxrt_coreutil` *before* the
   source file — GNU ld only resolves symbols against a library that
   appears after the object needing them, so linking failed until the
   flag order was fixed.
2. `stim_frame_sampler` needs `extern "C"` linkage, not just global scope
   (which cosimulation alone required — see `kernel/stim_frame_sampler.hpp`).
   sw_emu loads the compiled kernel as a shared library and looks up the
   literal string `"stim_frame_sampler"` via dlsym; a C++-mangled name
   doesn't match. `extern "C"` only affects the exported symbol name, not
   the type system, so this didn't require touching how the kernel is
   called or its C++-typed parameters.

**`hw` has been attempted three times** (`make hw`), ~10 hours of real
Vivado synthesis + implementation total against `xcu55c-fsvh2892-2L-e` —
confirming the project brief's "potentially hours long" warning every
time. Each produced a valid `.xclbin` with excellent, consistent
post-route resource usage (~2.6x *better* than HLS's own estimate — see
`../docs/utilization.md`), but timing has not closed:

1. 300 MHz target: WNS -0.688ns, ~249 MHz achievable.
2. Retargeted to 250 MHz -- except the retarget didn't actually apply
   (`--kernel_frequency` needs to be on both `v++ -c` and `-l`; it was
   only on `-c`). Caught by checking the routed report's actual clock
   period directly rather than trusting the intended change, which
   turned out to matter: WNS got *worse* (-1.092ns), which was run-to-run
   placement noise on an unchanged real target, not evidence the retarget
   idea was wrong.
3. Same 250 MHz target, fix applied for real (confirmed via the routed
   report showing `period=4.000ns`): WNS improved to **-0.179ns** — a
   ~74% cut in the violation, genuine progress, still short of closing.

All three runs' failing paths point at the same region: the Philox
noise-generator logic (`draw_noise`), heavily replicated across 64 shot
lanes. Not run on physical hardware at any point — an unclosed-timing
bitstream isn't a meaningful correctness check. Full account of all
three attempts, including each failing path, in `../docs/utilization.md`.
Closing the remaining ~0.18ns gap likely needs something more targeted
than another clock-target guess (a placement constraint on the Philox
block, or an extra `phys_opt_design` pass aimed at it) — each attempt
costs another multi-hour build, so treat further iteration as a
deliberate decision, not something to trigger incidentally.
