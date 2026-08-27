"""Bit-exact Python reference model of the stim-u55c kernel.

This module is the Tier 2 oracle (see top-level README.md, "Validation
strategy"): kernel output must match this module's output bit-for-bit
given the same instruction stream and the same counter-based PRNG seed.

Phase 0 scope: this file is scaffolding only. Frame propagation, the
counter-based PRNG, and the detector fold described in the project brief
are built out in Phase 1. What's here now is the one property Phase 1's
implementation is required to preserve: with all noise channels disabled,
every detector fires zero, for every shot, always (Tier 1).
"""

from __future__ import annotations

import stim


def noiseless_detectors_are_all_zero(circuit: stim.Circuit, *, shots: int = 256) -> bool:
    """True iff every detector reads zero on every shot of a noiseless circuit.

    A nonzero detector on a noiseless circuit is a bug in frame propagation
    or detector folding, never a legitimate result (Tier 1). Until the
    soft model itself exists (Phase 1), this checks the property against
    upstream Stim as the baseline the soft model will be required to match.
    """
    sampler = circuit.compile_detector_sampler()
    detectors = sampler.sample(shots=shots)
    return not detectors.any()
