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

**sw_emu is confirmed working**: `make sw_emu && ./run_and_validate.sh
sw_emu` builds and runs end-to-end, bit-exact against the soft model,
through the real XRT host runtime — not just C-sim or HLS cosimulation.
Two real bugs this surfaced, neither in the kernel logic itself:
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

**hw_emu and hw are not yet attempted.** hw_emu needs full RTL simulation
of the kernel *and* the platform's PCIe/XDMA/HBM shell (more than the
kernel-only cosimulation in `kernel/hls/`, whose time cost is already
documented in `../docs/utilization.md`), and `hw` is a real Vivado
synthesis + implementation run that the project brief flags as
potentially hours long — never start it before hw_emu is green, and treat
the time commitment as worth flagging before running it, not something
to trigger incidentally.
