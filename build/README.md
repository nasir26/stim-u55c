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

**`hw` has been attempted** (`make hw`): a real Vivado synthesis +
implementation run against `xcu55c-fsvh2892-2L-e`, completing in 3h 53m —
confirming the project brief's "potentially hours long" warning exactly.
Result: a valid `.xclbin`, excellent post-route resource usage (~2.6x
*better* than HLS's own estimate — see `../docs/utilization.md`), but
timing **not** closed (WNS -0.688ns, ~249 MHz achievable vs. this
project's 250 MHz floor). The failing path is diagnosed, not vague:
routing delay on a reset-fanout path into the Philox modulo-divider
hardware, not a logic or resource problem. Not run on physical hardware
— an unclosed-timing bitstream isn't a meaningful correctness check.
Full account in `../docs/utilization.md`. Re-running `hw` (e.g. with a
placement constraint on that reset net, or a lower, safely-closing clock
target) costs another multi-hour build each time, so treat that as a
deliberate decision, not something to trigger incidentally.
