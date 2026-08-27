# stim-u55c build orchestration.
#
# sw_emu, hw_emu, hw: not implemented yet -- kernel/ is empty by design
# until Phase 2 (see top-level README.md "Phased plan"). They land in
# that order, each gated on the previous stage passing, per the project's
# working rules: never start an hw build until hw_emu is green.
#
# test: real today -- runs the CPU-only soft-model-vs-Stim suite that CI
# also runs (Phase 0 gate).

.PHONY: sw_emu hw_emu hw test bench clean

test:
	cd .. && pytest -v

sw_emu hw_emu hw bench:
	$(error $@ is not implemented yet -- see ../README.md "Phased plan"; kernel/ has no sources until Phase 2)

clean:
	rm -rf _x .Xil *.log *.jou emconfig.json
