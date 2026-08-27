# stim-u55c build orchestration.
#
# test: real today -- runs everything pytest covers, which as of Phase 2
# includes the kernel's own C-sim testbenches (plain g++, no Vitis --
# see kernel/ap_uint_shim.hpp) alongside the soft-model-vs-Stim suite.
# This is Phase 2's gate (kernel bit-exact vs. the soft model), not a
# real v++ sw_emu run -- see sw_emu below.
#
# hls-synth, hls-cosim: local-only, need a sourced Vitis HLS install (not
# in CI -- see ../.github/workflows/ci.yml). Real vitis_hls C-synthesis /
# C-RTL cosimulation of the kernel; results as of Phase 3 are in
# ../docs/utilization.md. hls-cosim needs a test vector generated first
# (kernel/hls/generate_test_vector.py) if kernel/hls/test_vectors/ is
# missing -- it isn't committed, see .gitignore.
#
# sw_emu, hw_emu, hw: not implemented yet. A real v++ sw_emu build needs
# host/ (the XRT runtime + instruction-stream DMA setup) and a v++
# kernel wrapper around stim_frame_sampler.cpp, neither of which exist
# yet -- that's Phase 4. They land in sw_emu -> hw_emu -> hw order, each
# gated on the previous stage passing, per the project's working rules:
# never start an hw build until hw_emu is green.

.PHONY: sw_emu hw_emu hw test bench clean hls-synth hls-cosim

test:
	cd .. && pytest -v

hls-synth:
	cd ../kernel/hls && vitis_hls -f run_hls.tcl

hls-cosim:
	cd ../kernel/hls && test -f test_vectors/instructions.bin || python3 generate_test_vector.py
	cd ../kernel/hls && STIM_U55C_HLS_COSIM=1 vitis_hls -f run_hls.tcl

sw_emu hw_emu hw bench:
	$(error $@ is not implemented yet -- see ../README.md "Phased plan"; needs host/, which doesn't exist until Phase 4)

clean:
	rm -rf _x .Xil *.log *.jou emconfig.json
	rm -rf ../kernel/hls/stim_frame_sampler_hls ../kernel/hls/.Xil ../kernel/hls/test_vectors
