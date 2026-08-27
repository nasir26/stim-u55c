#!/usr/bin/env python3
"""Regenerates build/connectivity.cfg -- HBM bank assignment for the
stim_frame_sampler kernel's memory-mapped arguments. Per the project
brief, this is generated rather than handwritten so bank counts stay one
variable to tune, not four scattered edits. Run after changing the
kernel's argument list or INTERFACE pragmas (kernel/stim_frame_sampler.cpp).

Starts at 4 of the U55C's 32 HBM pseudo-channels, well under the "at most
8 banks" ceiling the project brief sets from prior experience with
Vivado level-7 routing congestion on this card at 16 banks -- expand only
after timing closes, per that same guidance.
"""

from pathlib import Path

# argument name -> HBM bank. One argument per bank even though
# instructions/layer_offsets share an m_axi bundle (gmem0) and
# detector_out/observable_out share another (gmem1) in the kernel's
# INTERFACE pragmas -- v++ assigns banks per argument, not per bundle.
_KERNEL_NAME = "stim_frame_sampler"
_INSTANCE_NAME = "sampler_1"
_ARGUMENT_BANKS = {
    "instructions": 0,
    "layer_offsets": 1,
    "detector_out": 2,
    "observable_out": 3,
}
_CLOCK_HZ = 300_000_000  # matches kernel/hls/run_hls.tcl's CLOCK_PERIOD_NS target


def generate() -> str:
    lines = [
        "# GENERATED FILE -- do not edit by hand. Regenerate with:",
        "#   python3 build/generate_connectivity.py",
        "# Source of truth: build/generate_connectivity.py",
        "",
        "[connectivity]",
        f"nk={_KERNEL_NAME}:1:{_INSTANCE_NAME}",
    ]
    for arg, bank in _ARGUMENT_BANKS.items():
        lines.append(f"sp={_INSTANCE_NAME}.{arg}:HBM[{bank}]")
    lines += [
        "",
        "[hls]",
        f"clock={_CLOCK_HZ}:{_KERNEL_NAME}",
        "",
        "[vivado]",
        "prop=run.impl_1.STEPS.PHYS_OPT_DESIGN.IS_ENABLED=true",
        "prop=run.impl_1.STEPS.OPT_DESIGN.ARGS.DIRECTIVE=Explore",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    out = Path(__file__).resolve().parent / "connectivity.cfg"
    out.write_text(generate())
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
