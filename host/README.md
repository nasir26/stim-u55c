# host/

XRT host runtime: `xrt_runner.cpp` (Mode A bulk-throughput and Mode B
low-latency runners), `scheduler.cpp` (layer partitioning + instruction
stream encoding), `stim_bridge.cpp` (upstream Stim parse, reference
sample, DEM generation).

Empty as of Phase 0 by design — see the phased plan in the top-level
[README](../README.md). Populated starting Phase 2.
