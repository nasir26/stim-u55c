#!/usr/bin/env python3
"""Generate all paper figures from the project's own committed results.

Every number here is transcribed from docs/utilization.md and
bench/results/*.md (see the citations in each figure's construction
below) -- nothing is synthesized or estimated for presentation purposes.
Run from the paper/ directory: python3 make_figures.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrow, FancyBboxPatch
import numpy as np
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "font.size": 10,
    "font.family": "serif",
    "axes.grid": True,
    "grid.alpha": 0.3,
    "axes.axisbelow": True,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

GRAY = "#4d4d4d"
BLUE = "#2166ac"
RED = "#b2182b"
GREEN = "#1b7837"


# ---------------------------------------------------------------------
# Figure 1: system architecture / pipeline (schematic)
# ---------------------------------------------------------------------
def fig_architecture():
    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.6)
    ax.axis("off")

    def box(x, y, w, h, text, fc="#eef2f7", ec="#333333"):
        p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.08",
                            linewidth=1.1, edgecolor=ec, facecolor=fc)
        ax.add_patch(p)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8.6)
        return (x, y, w, h)

    def arrow(x1, y1, x2, y2, label=None, ls="-"):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                     arrowprops=dict(arrowstyle="-|>", lw=1.2, color="#222222", linestyle=ls))
        if label:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.18, label, ha="center", fontsize=7.4, color="#222222")

    # Host region
    ax.add_patch(mpatches.Rectangle((0.15, 3.55), 4.4, 1.85, fill=False, ec="#888888", ls="--", lw=1))
    ax.text(0.35, 5.15, "Host (CPU)", fontsize=8.8, weight="bold", color="#555555")

    b1 = box(0.4, 4.15, 1.9, 0.9, "Stim circuit\n+ noise model")
    b2 = box(2.5, 4.15, 1.9, 0.9, "kernel/isa.py\ncompile + layer")

    # FPGA region
    ax.add_patch(mpatches.Rectangle((0.15, 1.15), 9.65, 2.15, fill=False, ec="#888888", ls="--", lw=1))
    ax.text(0.35, 3.1, "Alveo U55C (FPGA)", fontsize=8.8, weight="bold", color="#555555")

    b3 = box(0.4, 1.4, 1.7, 1.3, "Philox4x32-10\nPRNG")
    b4 = box(2.35, 1.4, 2.5, 1.3, "Pauli frame\npropagation\n(gate ops)")
    b5 = box(5.1, 1.4, 2.2, 1.3, "Detector /\nobservable\nfold")
    b6 = box(7.55, 1.4, 2.0, 1.3, "b8-packed\nsyndrome\noutput")

    # Host decode region
    ax.add_patch(mpatches.Rectangle((5.35, 3.55), 4.4, 1.85, fill=False, ec="#888888", ls="--", lw=1))
    ax.text(5.55, 5.15, "Host (CPU)", fontsize=8.8, weight="bold", color="#555555")
    b7 = box(5.6, 4.15, 1.9, 0.9, "PyMatching\n(MWPM oracle)")
    b8 = box(7.75, 4.15, 1.9, 0.9, "Statistical /\nlogical-error\nchecks")

    arrow(2.3, 4.6, 2.5, 4.6)
    arrow(3.45, 4.15, 1.55, 2.7, "XRT DMA\n(instruction stream)")
    arrow(2.1, 2.05, 2.35, 2.05)
    arrow(4.85, 2.05, 5.1, 2.05)
    arrow(7.3, 2.05, 7.55, 2.05)
    arrow(8.55, 2.7, 6.5, 4.15, "XRT DMA\n(syndromes)")
    arrow(7.5, 4.6, 7.75, 4.6)

    ax.set_title("stim-u55c pipeline: circuit compilation, FPGA sampling, host decode", fontsize=9.6)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "architecture.pdf"))
    plt.close(fig)


# ---------------------------------------------------------------------
# Figure 2: WNS convergence across the five real-hardware attempts
# source: docs/utilization.md, five `hw` build attempts
# ---------------------------------------------------------------------
def fig_timing_closure():
    attempts = ["1\n300 MHz", "2\n\"250 MHz\"\n(misapplied)", "3\n250 MHz", "4\n+Aggressive-\nExplore", "5\n+NoTiming-\nRelaxation"]
    wns = [-0.688, -1.092, -0.179, -0.041, 0.000]
    failing = [26495, 40302, 10707, 1211, 0]
    hours = [3 + 53/60, 3 + 18/60, 3 + 14/60, 5 + 33/60, 4 + 19/60]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6.6, 5.0), sharex=True,
                                    gridspec_kw={"hspace": 0.12})

    colors = [RED, RED, RED, RED, GREEN]
    ax1.bar(attempts, wns, color=colors, edgecolor="black", linewidth=0.6)
    ax1.axhline(0, color="black", lw=0.8)
    ax1.set_ylabel("Worst negative slack (ns)")
    ax1.set_ylim(-1.25, 0.25)
    fig.suptitle("Real-hardware timing closure across five implementation attempts", fontsize=9.6, y=0.995)
    for i, v in enumerate(wns):
        ax1.text(i, v + (0.05 if v >= 0 else -0.05), f"{v:+.3f}", ha="center",
                  va="bottom" if v >= 0 else "top", fontsize=7.6)

    ax2.bar(attempts, failing, color=colors, edgecolor="black", linewidth=0.6)
    ax2.set_ylabel("Failing timing endpoints")
    for i, v in enumerate(failing):
        ax2.text(i, v + 500, f"{v:,}", ha="center", va="bottom", fontsize=7.6)
    ax2.set_xlabel("Attempt (cumulative build time " + ", ".join(f"{h:.1f}h" for h in hours) + f"; total ≈{sum(hours):.0f}h)")

    plt.setp(ax2.get_xticklabels(), fontsize=7.4)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(os.path.join(OUT, "timing_closure.pdf"))
    plt.close(fig)


# ---------------------------------------------------------------------
# Figure 3: HLS synthesis estimate vs. real post-route resource usage
# source: docs/utilization.md Phase 3 HLS estimate table and fifth hw attempt
# ---------------------------------------------------------------------
def fig_resource_estimate_vs_real():
    resources = ["LUT", "FF/REG", "DSP", "BRAM_18K"]
    hls_est = [217052, 174517, 960, 66]
    post_route = [83843, 101402, 708, 21]
    ratio = [p / h for p, h in zip(post_route, hls_est)]

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(7.4, 3.4))

    x = np.arange(len(resources))
    w = 0.35
    axL.bar(x - w / 2, hls_est, w, label="HLS estimate (Phase 3)", color="#9ecae1", edgecolor="black", linewidth=0.6)
    axL.bar(x + w / 2, post_route, w, label="Real post-route (timing-closed)", color=BLUE, edgecolor="black", linewidth=0.6)
    axL.set_yscale("log")
    axL.set_ylabel("Resource count (log scale)")
    axL.set_xticks(x)
    axL.set_xticklabels(resources, fontsize=8.4)
    axL.legend(fontsize=7, loc="upper right")
    axL.set_title("Absolute counts", fontsize=9)

    axR.bar(x, ratio, color=GREEN, edgecolor="black", linewidth=0.6)
    axR.axhline(1.0, color="black", lw=0.8, ls="--")
    axR.set_ylim(0, 1.1)
    axR.set_ylabel("Post-route ÷ HLS-estimate ratio")
    axR.set_xticks(x)
    axR.set_xticklabels(resources, fontsize=8.4)
    axR.set_title("HLS overestimation factor", fontsize=9)
    for i, v in enumerate(ratio):
        axR.text(i, v + 0.02, f"{v:.2f}×", ha="center", fontsize=7.6)

    fig.suptitle("HLS synthesis estimate vs. real post-route utilization", fontsize=9.8)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(os.path.join(OUT, "resource_estimate_vs_real.pdf"))
    plt.close(fig)


# ---------------------------------------------------------------------
# Figure 4: Mode A throughput, FPGA vs CPU Stim
# source: bench/results/2026-09-01-mode-a-throughput.md
# ---------------------------------------------------------------------
def fig_throughput():
    circuits = ["repetition\ncode d=3", "surface\ncode d=3", "surface\ncode d=5"]
    fpga = [865117, 160104, 33587]
    cpu = [4867590, 2260033, 512610]
    speedup = [4867590 / 865117, 2260033 / 160104, 512610 / 33587]

    fig, ax = plt.subplots(figsize=(6.2, 3.4))
    x = np.arange(len(circuits))
    w = 0.35
    ax.bar(x - w / 2, fpga, w, label="FPGA (Alveo U55C, 250 MHz, Mode A)", color=BLUE, edgecolor="black", linewidth=0.6)
    ax.bar(x + w / 2, cpu, w, label="CPU (Stim, EPYC 7742, single-core)", color="#fdae61", edgecolor="black", linewidth=0.6)
    ax.set_yscale("log")
    ax.set_ylabel("Shots / second (log scale)")
    ax.set_xticks(x)
    ax.set_xticklabels(circuits, fontsize=8.6)
    ax.legend(fontsize=7.6)
    for i, s in enumerate(speedup):
        ax.text(i, max(fpga[i], cpu[i]) * 1.4, f"{s:.1f}×\nCPU", ha="center", fontsize=7.4, color="#333333")
    ax.set_title("Mode A throughput: FPGA vs. single-core CPU Stim (SHOTS=64/launch)", fontsize=9.4)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "throughput.pdf"))
    plt.close(fig)


# ---------------------------------------------------------------------
# Figure 5: logical error rate vs physical error rate, Tier 5
# source: bench/results/2026-09-02-tier5-logical-error-rate.md
# ---------------------------------------------------------------------
def fig_logical_error_rate():
    p = np.array([0.001, 0.003, 0.01])
    d3_fpga = np.array([0.00074, 0.00651, 0.05906])
    d3_cpu = np.array([0.00079, 0.00662, 0.05919])
    d5_fpga = np.array([0.00013, 0.00331, 0.08412])
    d5_cpu = np.array([0.00016, 0.00332, 0.08395])

    fig, ax = plt.subplots(figsize=(5.4, 4.0))
    ax.plot(p, d3_cpu, "-", color=GRAY, lw=1.3, zorder=1)
    ax.plot(p, d5_cpu, "-", color=GRAY, lw=1.3, zorder=1, label="CPU Stim + PyMatching")
    ax.plot(p, d3_fpga, "o", color=BLUE, ms=7, label="FPGA, d=3", zorder=3)
    ax.plot(p, d5_fpga, "s", color=RED, ms=7, label="FPGA, d=5", zorder=3)
    ax.plot(p, d3_cpu, "x", color=BLUE, ms=7, mew=1.6, zorder=3)
    ax.plot(p, d5_cpu, "x", color=RED, ms=7, mew=1.6, zorder=3)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Physical error rate $p$")
    ax.set_ylabel("Logical error rate")
    ax.set_title("Tier 5: logical error rate, FPGA syndromes vs. CPU Stim\n(surface code, rotated memory Z, 10⁶ shots/point)", fontsize=9)
    ax.legend(fontsize=7.6, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "logical_error_rate.pdf"))
    plt.close(fig)


if __name__ == "__main__":
    fig_architecture()
    fig_timing_closure()
    fig_resource_estimate_vs_real()
    fig_throughput()
    fig_logical_error_rate()
    print("Figures written to", OUT)
