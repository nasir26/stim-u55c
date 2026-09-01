# Validation tiers on real hardware

Everything below runs against the timing-closed `build/hw/stim_frame_sampler.xclbin`
(`docs/utilization.md`'s fifth `hw` attempt, WNS 0.000ns) on a physical
Alveo U55C, not emulation. Same three circuits used throughout this
project's validation since Phase 1/2 (repetition code d=3, surface code
d=3 and d=5, plus surface code d=3 in the X basis for Tier 3).

Reproduce: `bench/hw_tier3.py`, `bench/hw_tier4.py` (need a built
`build/hw/` — see `build/README.md`). Tier 1/2 were run ad hoc via
`build/hw/xrt_runner` on noiseless and normal instruction streams
respectively (see commit history around 2026-09-01 for the exact
commands); not (yet) wrapped into a committed script the way Tiers 3/4
are.

## Results

| Tier | What | Circuits | Result |
|---|---|---|---|
| 1 | Noiseless determinism | rep d3, surface d3, surface d5 | **PASS** — all detector/observable words exactly zero, all 64 shot lanes |
| 2 | Bit-exact vs. soft model | rep d3, surface d3, surface d5 | **PASS** — `docs/utilization.md`'s fifth-attempt entry |
| 3 | Single-fault injection vs. DEM | rep d3, surface z d3, surface x d3 | **PASS** — 458/458 DEM error mechanisms, ~92s |
| 4 | Statistical equivalence vs. CPU Stim | rep d3, surface d3, surface d5 | **PASS** — 10,000,000 shots/circuit, max\|z\| 1.64 / 2.91 / 2.64 (5σ bar), ~6m 42s total |
| 5 | Logical error rate vs. Stim+PyMatching | — | **not attempted** |

Tiers 1-4 above are the real-hardware counterparts of validation that
already passed in software since Phase 1 (Tiers 1/3/4,
`tests/test_softmodel_validation.py`) and Phase 2/3 (Tier 2, C-sim and
RTL cosimulation). What's new here is running the *same* checks through
the actual synthesized kernel on physical silicon rather than a model of
it.

## Tier 3 methodology note

The kernel has no "fault injection mode" — Tier 3 needs an actual
instruction stream with a forced, deterministic single Pauli error and
nothing else. `softmodel/reference_sampler.py:build_single_fault_circuit`
builds one: given a `stim.CircuitErrorLocation`'s `stack_frames` and
`flipped_pauli_product` (same location format Tier 3 has used since
Phase 1), it walks the original circuit with the same path-matching logic
`sample_single_fault` already uses to *interpret* a fault, but emits an
actual `stim.Circuit` instead — noise stripped everywhere except an
explicit `p=1` `X_ERROR`/`Y_ERROR`/`Z_ERROR` at the matched location.
That circuit goes through the ordinary, unmodified `kernel.isa.encode_circuit`
and runs on the ordinary, unmodified kernel — no isa.py or kernel changes
needed for Tier 3 to reach real hardware.

Before trusting this on ~92 seconds of real hardware time, it was
cross-checked against `sample_single_fault` (the already-validated
Phase 1 interpreter) for the same 458 DEM mechanisms: 0 disagreements.

## Tier 5 (not attempted): what it needs

Full Tier 5 needs `pymatching.Matching.from_detector_error_model`,
sweeps across d = 3, 5, 7, 9, 11 (the current kernel's `NUM_QUBITS_MAX =
128` covers d≤5 — d=11 alone needs 274 qubits, so this needs a config
change *and* a new timing-closed `hw` build before it can run at all),
multiple physical error rates per circuit, and enough shots per point
for the resulting logical error rate curve to be statistically
comparable against Stim+PyMatching's own curve. Real, scoped, separate
work — not attempted this pass given the additional `NUM_QUBITS_MAX`
rebuild it requires (another multi-hour `hw` build, per
`docs/utilization.md`'s experience getting the *current* build to close
timing).
