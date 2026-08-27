# host/

XRT host runtime.

- `xrt_runner.cpp` — Mode A (bulk throughput): loads a compiled
  instruction stream (`kernel/isa.py:Program.serialize()`), runs it on
  the real `stim_frame_sampler` kernel via XRT (works unchanged against
  sw_emu, hw_emu, or real hardware — see `../build/vpp_build.sh`), and
  writes raw detector/observable output in the same format
  `kernel/hls_testbench/tb_stim_frame_sampler.cpp` does, so the same
  Python-side comparison against `softmodel/kernel_replay.py` validates
  both. See its own header comment for why the packed instruction file
  gets parsed into native `Instruction` structs before it's DMA'd to the
  device, rather than copied as-is.
- Mode B (low-latency, polled `xrt::run::state()`, host-memory bridge) is
  a separate runtime — Phase 5, not written yet.
- `scheduler.cpp` / `stim_bridge.cpp` from the original repo layout
  aren't separate files here: instruction-stream compiling and layer
  scheduling live in `kernel/isa.py` (Python), and Stim parsing/reference
  sampling in `softmodel/reference_sampler.py` — see those modules' own
  docstrings for why keeping them in Python was the right call rather
  than porting to C++ for its own sake.
