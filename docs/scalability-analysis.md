# Analisis Skalabilitas Algoritma KPB

Sesuai masukan dosen + perbaikan dataset:

## 1. Dataset

### Suite A — GoCJ resmi / official-method (100 … 1000, kelipatan 100)
| File | Keterangan |
|------|------------|
| `GoCJ_Dataset_100.txt` … `GoCJ_Dataset_1000.txt` | 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000 |

Sumber: file resmi Mendeley (100/500/1000) + generate metode paper (Monte Carlo + seed `Original_DataSet`) untuk ukuran yang hilang.

### Suite B — Synthetic (1000 … 10.000, kelipatan 1000) — **termasuk 1000**
| File | Keterangan |
|------|------------|
| `synthetic/Synthetic_GoCJ_1000.txt` … `Synthetic_GoCJ_10000.txt` | Resample distribusi empiris GoCJ_1000 |

## 2. Metrik & runner

| Runner | Cakupan | Output |
|--------|---------|--------|
| **Analytic KPB** (`scripts/run_scalability_experiment.py`) | Semua size × k=20/50/100 | `results/simulation/summary_scalability.csv` + 5 PNG |
| **CloudSim Plus** (`scripts/run_cloudsim_batch.ps1` / `.sh`) | Official 100–1000 + Synthetic (batch) | `results/simulation/cloudlets_*.csv`, `log_*.txt`, `summary.csv` |
| **Real-world Docker** (`scripts/run_realworld_batch.ps1`) | Official 100–1000 + Synthetic_1000 | `realworld/results/` |

CloudSim sudah dijalankan untuk **official 200–900** dan **Synthetic_1000** (selisih vs analitik ~1–2%, konsisten README §6.2).

## 3. Cara menjalankan ulang

```powershell
# Analytic + diagram (cepat)
python scripts/run_scalability_experiment.py

# CloudSim penuh (butuh JDK + folder lib/)
powershell -ExecutionPolicy Bypass -File scripts\run_cloudsim_batch.ps1

# Real-world (butuh Docker compose up)
cd realworld
docker compose up -d --build
powershell -ExecutionPolicy Bypass -File ..\scripts\run_realworld_batch.ps1
```

## 4. Temuan utama

1. Makespan & energi **linear** terhadap jumlah task (plot log-log).
2. **k=100%** terbaik untuk makespan, energi, utilisasi, biaya.
3. k=20% → utilisasi ~20%, makespan ~1.8× lebih buruk.
4. CloudSim ≈ analitik (selisih < 2%).
5. Scheduling time tetap ringan (~45–70 ms untuk 10.000 task, analytic).

## 5. Diagram

| File | Isi |
|------|-----|
| `results/figures/compare_100_1000.png` | Official GoCJ 100–1000 |
| `results/figures/compare_1000_10000.png` | Synthetic 1000–10.000 |
| `results/figures/bars_*.png` | Bar chart |
| `results/figures/compare_loglog_all.png` | Log-log makespan & energi |
