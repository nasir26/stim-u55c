# stim-u55c build orchestration.
#
# test: real today -- runs everything pytest covers, which as of Phase 2
# includes the kernel's own C-sim testbenches (plain g++, no Vitis --
# see kernel/ap_uint_shim.hpp) alongside the soft-model-vs-Stim suite.
# This is Phase 2's actual gate (kernel bit-exact vs. the soft model),
# not a real v++ sw_emu run -- see sw_emu below.
#
# sw_emu, hw_emu, hw: not implemented yet. A real v++ sw_emu build needs
# host/ (the XRT runtime + instruction-stream DMA setup) and a v++
# kernel wrapper around stim_frame_sampler.cpp, neither of which exist
# yet -- that's Phase 4. They land in sw_emu -> hw_emu -> hw order, each
# gated on the previous stage passing, per the project's working rules:
# never start an hw build until hw_emu is green.

.PHONY: sw_emu hw_emu hw test bench clean

test:
	cd .. && pytest -v

sw_emu hw_emu hw bench:
	$(error $@ is not implemented yet -- see ../README.md "Phased plan"; needs host/, which doesn't exist until Phase 4)

clean:
	rm -rf _x .Xil *.log *.jou emconfig.json
