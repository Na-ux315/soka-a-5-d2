#!/usr/bin/env python3
"""
Scalability experiment for KPB scheduler (SOKA A-5).
- Uses existing GoCJ datasets where available (100, 500, 1000).
- Generates synthetic datasets for 100..1000 step 100 and 1000..10000 step 1000
  by resampling the empirical distribution of GoCJ_Dataset_1000.
- Runs pure-analytic KPB (matches design FitnessEvaluator + KpbScheduler).
- Energy model approximates CloudSim design: 6 hosts always powered until makespan,
  utilization derived from VM finish times mapped to hosts via fixed placement.
- Produces summary CSV + comparison plots (makespan, energy, response, util, DI, throughput, cost, sched time).
"""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "src" / "main" / "resources" / "dataset"
SYNTH_DIR = DATASET_DIR / "synthetic"
OUT_DIR = ROOT / "results" / "simulation"
FIG_DIR = ROOT / "results" / "figures"
SUMMARY_CSV = OUT_DIR / "summary_scalability.csv"

# --- Infrastructure from design (VmFactory + DatacenterFactory + placement.csv) ---
# VM capacity = PE * MIPS/PE
VM_CAPACITIES = np.array(
    [10000.0] * 4 + [3000.0] * 8 + [1000.0] * 8, dtype=float
)  # 20 VMs: V3x4, V2x8, V1x8

# Host assignment from placement.csv (vm -> host index 0..5)
# Hosts 0,1,2 = Type A (Performance, DC1), 3,4,5 = Type B (Efficiency, DC2)
VM_TO_HOST = np.array(
    [
        0, 1, 2, 0,  # V3: vm0-3
        1, 2, 1, 2,  # V2 on DC1: vm4-7
        3, 4, 5, 3,  # V2 on DC2: vm8-11
        4, 5, 4, 5, 3, 4, 5, 3,  # V1: vm12-19
    ],
    dtype=int,
)

# Host power model (W): (P_idle, P_max)
HOST_POWER = [
    (175.0, 250.0),  # A0
    (175.0, 250.0),  # A1
    (175.0, 250.0),  # A2
    (72.0, 120.0),  # B0
    (72.0, 120.0),  # B1
    (72.0, 120.0),  # B2
]

# Host PE capacity for utilization (design)
HOST_PES = [8, 8, 8, 8, 8, 8]
# VM PE counts for utilization estimate
VM_PES = np.array([4] * 4 + [2] * 8 + [1] * 8, dtype=float)

# Cost rates from design (approximate analytic cost over makespan)
# DC1 cost/s = 0.05, DC2 = 0.03 for processing; we use VM-weighted proxy matching README scale.
# Better: cost ≈ sum over VMs of (cost_per_second_of_dc * makespan) for used capacity fraction.
# README numbers: for 100 tasks k=100 ~ $345. We'll calibrate a simple linear model.
# Using: total_cost = makespan * sum_host_cost_rate * (1 + util_factor)
# Simpler proxy used in many papers: cost proportional to makespan * sum of VM MIPS rates.
# We'll compute a design-consistent processing cost:
# DC1 hosts cost 0.05 $/s, DC2 0.03 $/s for the whole host lifetime to makespan.
HOST_COST_PER_S = [0.05, 0.05, 0.05, 0.03, 0.03, 0.03]
# RAM cost roughly proportional; README includes CPU+RAM+BW. Scale factor fitted so
# analytic matches README order of magnitude for n=100 k=100 (~345).
COST_SCALE = 1.0  # host processing cost alone for 233s * (3*0.05+3*0.03)=233*0.24≈56; too low
# Include memory/BW: use multiplier from observed README ratio ≈ 345/56 ≈ 6.16
COST_MULTIPLIER = 6.16


def load_lengths(path: Path) -> np.ndarray:
    vals: List[float] = []
    for line in path.read_text().splitlines():
        content = line.split("#", 1)[0].strip()
        if not content:
            continue
        for tok in content.replace(";", " ").replace(",", " ").split():
            vals.append(float(tok))
    return np.asarray(vals, dtype=float)


def generate_synthetic(base: np.ndarray, n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.choice(base, size=n, replace=True)


def kpb_schedule(task_lengths: np.ndarray, vm_cap: np.ndarray, k_percent: float) -> Tuple[np.ndarray, float]:
    """KPB as in KpbScheduler.java. Returns mapping and wall-clock scheduling ms."""
    t0 = time.perf_counter()
    m = len(vm_cap)
    subset = max(1, min(m, int(np.ceil(k_percent / 100.0 * m))))
    ready = np.zeros(m, dtype=float)
    mapping = np.empty(len(task_lengths), dtype=int)

    for i, length in enumerate(task_lengths):
        etc = length / vm_cap
        # rank by execution time ascending (stable)
        order = np.argsort(etc, kind="mergesort")
        candidates = order[:subset]
        finishes = ready[candidates] + etc[candidates]
        best_idx = int(np.argmin(finishes))
        vm = int(candidates[best_idx])
        mapping[i] = vm
        ready[vm] = ready[vm] + etc[vm]

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return mapping, elapsed_ms


def evaluate(
    task_lengths: np.ndarray,
    mapping: np.ndarray,
    vm_cap: np.ndarray,
    scheduling_ms: float,
    k_percent: float,
    dataset_name: str,
) -> Dict:
    n = len(task_lengths)
    m = len(vm_cap)
    # finish time per task = ready after assignment (recompute chronologically)
    ready = np.zeros(m, dtype=float)
    finish_task = np.zeros(n, dtype=float)
    for i, length in enumerate(task_lengths):
        vm = mapping[i]
        etc = length / vm_cap[vm]
        ready[vm] += etc
        finish_task[i] = ready[vm]

    vm_finish = ready.copy()
    makespan = float(vm_finish.max()) if n else 0.0
    avg_response = float(finish_task.mean()) if n else 0.0
    utilization = (
        100.0 * float(vm_finish.sum()) / (m * makespan) if makespan > 0 else 0.0
    )

    def di(times: np.ndarray) -> float:
        if len(times) == 0:
            return 0.0
        avg = times.mean()
        if avg == 0:
            return 0.0
        return float((times.max() - times.min()) / avg)

    di_all = di(vm_finish)
    used = vm_finish[vm_finish > 0]
    di_used = di(used)
    throughput = n / makespan if makespan > 0 else 0.0

    # Energy: host utilization over [0, makespan]
    # Approximate host CPU util as (sum PE of VMs on host that are busy) / host PE,
    # busy fraction ≈ vm_finish[vm] / makespan for each VM on host.
    energy_j = 0.0
    for h in range(6):
        p_idle, p_max = HOST_POWER[h]
        vms_on_h = np.where(VM_TO_HOST == h)[0]
        if makespan <= 0:
            continue
        # time-averaged PE utilization
        pe_busy = 0.0
        for vm in vms_on_h:
            pe_busy += VM_PES[vm] * (vm_finish[vm] / makespan)
        u = min(1.0, pe_busy / HOST_PES[h])
        # constant average util integration (conservative; design samples dynamically)
        power = p_idle + (p_max - p_idle) * u
        energy_j += power * makespan  # Joules if power in W and time in s

    energy_kwh = energy_j / 3_600_000.0

    # Cost: host cost rates * makespan * multiplier (fits design table scale)
    cost = makespan * sum(HOST_COST_PER_S) * COST_MULTIPLIER

    return {
        "dataset": dataset_name,
        "tasks": n,
        "k_percent": k_percent,
        "makespan_s": makespan,
        "energy_kwh": energy_kwh,
        "avg_response_s": avg_response,
        "utilization_pct": utilization,
        "di_all_vm": di_all,
        "di_used_vm": di_used,
        "throughput_task_s": throughput,
        "cost_usd": cost,
        "scheduling_ms": scheduling_ms,
    }


def ensure_datasets(base_lengths: np.ndarray) -> Dict[int, Path]:
    """Return map size -> path for all required sizes."""
    SYNTH_DIR.mkdir(parents=True, exist_ok=True)
    paths: Dict[int, Path] = {}

    # Official-style GoCJ for 100..1000 (step 100); synthetic only for large scale
    sizes_small = list(range(100, 1001, 100))  # 100..1000
    sizes_large = list(range(1000, 10001, 1000))  # 1000..10000
    all_sizes = sorted(set(sizes_small + sizes_large))

    for n in all_sizes:
        official = DATASET_DIR / f"GoCJ_Dataset_{n}.txt"
        if n <= 1000 and official.exists():
            paths[n] = official
            print(f"  using official GoCJ_Dataset_{n}.txt")
            continue
        # Large scale (>1000) or missing: synthetic resample
        out = SYNTH_DIR / f"Synthetic_GoCJ_{n}.txt"
        if not out.exists():
            data = generate_synthetic(base_lengths, n, seed=42 + n)
            out.write_text("\n".join(str(int(x)) for x in data) + "\n")
            print(f"  generated {out.name} (n={n})")
        paths[n] = out
        print(f"  using synthetic for n={n}")
    return paths


def plot_metrics(rows: List[Dict], sizes: List[int], title_suffix: str, outfile: Path) -> None:
    k_values = [20.0, 50.0, 100.0]
    metrics = [
        ("makespan_s", "Makespan (s)"),
        ("energy_kwh", "Energy (kWh)"),
        ("avg_response_s", "Avg Response (s)"),
        ("utilization_pct", "Utilization (%)"),
        ("di_all_vm", "Degree of Imbalance"),
        ("throughput_task_s", "Throughput (task/s)"),
        ("cost_usd", "Cost (USD)"),
        ("scheduling_ms", "Scheduling Time (ms)"),
    ]

    fig, axes = plt.subplots(2, 4, figsize=(16, 8))
    axes = axes.ravel()
    markers = {20.0: "o", 50.0: "s", 100.0: "^"}
    colors = {20.0: "#1f77b4", 50.0: "#ff7f0e", 100.0: "#2ca02c"}

    by_k: Dict[float, List[Dict]] = {k: [] for k in k_values}
    for r in rows:
        if r["tasks"] in sizes:
            by_k[r["k_percent"]].append(r)

    for ax, (key, ylabel) in zip(axes, metrics):
        for k in k_values:
            series = sorted(by_k[k], key=lambda x: x["tasks"])
            xs = [r["tasks"] for r in series]
            ys = [r[key] for r in series]
            ax.plot(
                xs,
                ys,
                marker=markers[k],
                color=colors[k],
                label=f"k={int(k)}%",
                linewidth=2,
            )
        ax.set_xlabel("Number of tasks")
        ax.set_ylabel(ylabel)
        ax.set_title(ylabel)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)

    fig.suptitle(f"KPB Scalability Comparison — {title_suffix}", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {outfile}")


def plot_grouped_bars(rows: List[Dict], sizes: List[int], outfile: Path) -> None:
    """Bar chart for key metrics at selected sizes."""
    k_values = [20.0, 50.0, 100.0]
    key_metrics = [
        ("makespan_s", "Makespan (s)"),
        ("energy_kwh", "Energy (kWh)"),
        ("throughput_task_s", "Throughput (task/s)"),
        ("utilization_pct", "Utilization (%)"),
    ]
    # pick a subset of sizes for readability
    if max(sizes) <= 1000:
        show = [100, 200, 300, 500, 700, 1000]
    else:
        show = [1000, 2000, 4000, 6000, 8000, 10000]
    show = [s for s in show if s in sizes]

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    axes = axes.ravel()
    x = np.arange(len(show))
    width = 0.25
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]

    lookup = {(r["tasks"], r["k_percent"]): r for r in rows}

    for ax, (key, ylabel) in zip(axes, key_metrics):
        for i, k in enumerate(k_values):
            ys = [lookup[(s, k)][key] for s in show]
            ax.bar(x + i * width, ys, width, label=f"k={int(k)}%", color=colors[i])
        ax.set_xticks(x + width)
        ax.set_xticklabels([str(s) for s in show])
        ax.set_xlabel("Number of tasks")
        ax.set_ylabel(ylabel)
        ax.set_title(ylabel)
        ax.legend()
        ax.grid(True, axis="y", alpha=0.3)

    fig.suptitle("KPB Metric Comparison by Dataset Size & k%", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {outfile}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    base_path = DATASET_DIR / "GoCJ_Dataset_1000.txt"
    base = load_lengths(base_path)
    print(f"Base distribution from {base_path.name}: n={len(base)}, mean={base.mean():.0f}")

    print("Ensuring datasets...")
    paths = ensure_datasets(base)

    sizes_small = list(range(100, 1001, 100))
    sizes_large = list(range(1000, 10001, 1000))
    k_values = [20.0, 50.0, 100.0]

    rows: List[Dict] = []
    print("Running experiments...")
    for n in sorted(set(sizes_small + sizes_large)):
        lengths = load_lengths(paths[n])
        assert len(lengths) == n, (n, len(lengths))
        name = paths[n].stem
        for k in k_values:
            mapping, sched_ms = kpb_schedule(lengths, VM_CAPACITIES, k)
            row = evaluate(lengths, mapping, VM_CAPACITIES, sched_ms, k, name)
            rows.append(row)
            print(
                f"  n={n:5d} k={int(k):3d}%  makespan={row['makespan_s']:10.2f}s  "
                f"energy={row['energy_kwh']:.4f} kWh  util={row['utilization_pct']:.1f}%  "
                f"sched={row['scheduling_ms']:.2f} ms"
            )

    # Write CSV
    fieldnames = [
        "dataset",
        "tasks",
        "k_percent",
        "makespan_s",
        "energy_kwh",
        "avg_response_s",
        "utilization_pct",
        "di_all_vm",
        "di_used_vm",
        "throughput_task_s",
        "cost_usd",
        "scheduling_ms",
    ]
    with SUMMARY_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"Wrote {SUMMARY_CSV}")

    # Plots
    plot_metrics(rows, sizes_small, "GoCJ / Synthetic 100–1000", FIG_DIR / "compare_100_1000.png")
    plot_metrics(rows, sizes_large, "Synthetic 1000–10000", FIG_DIR / "compare_1000_10000.png")
    plot_grouped_bars(rows, sizes_small, FIG_DIR / "bars_100_1000.png")
    plot_grouped_bars(rows, sizes_large, FIG_DIR / "bars_1000_10000.png")

    # Combined makespan & energy focus plot
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, key, ylabel in zip(
        axes,
        ["makespan_s", "energy_kwh"],
        ["Makespan (s)", "Energy (kWh)"],
    ):
        for k, style in [(20.0, "o-"), (50.0, "s-"), (100.0, "^-")]:
            series = sorted([r for r in rows if r["k_percent"] == k], key=lambda x: x["tasks"])
            ax.plot(
                [r["tasks"] for r in series],
                [r[key] for r in series],
                style,
                label=f"k={int(k)}%",
                linewidth=2,
            )
        ax.set_xlabel("Number of tasks")
        ax.set_ylabel(ylabel)
        ax.set_title(ylabel)
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_xscale("log")
        ax.set_yscale("log")
    fig.suptitle("KPB Scalability (log-log) — Makespan & Energy", fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out = FIG_DIR / "compare_loglog_all.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out}")

    print("\nDone. Results in results/simulation/ and results/figures/")


if __name__ == "__main__":
    main()
