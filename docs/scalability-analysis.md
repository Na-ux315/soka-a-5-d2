# Analisis Skalabilitas Algoritma KPB

Sesuai masukan dosen:
1. Uji coba dataset **100, 200, 300, …, 1000**
2. Dataset synthetic **1000, 2000, …, 10.000**
3. Diagram perbandingan makespan, energi, dan metrik lain

## Metode

- **Dataset asli GoCJ**: 100, 500, 1000 (dari `src/main/resources/dataset/`).
- **Dataset synthetic**: resampling distribusi empiris `GoCJ_Dataset_1000` (seed deterministik) → file di `src/main/resources/dataset/synthetic/`.
- **Scheduler**: implementasi analitik KPB identik dengan `KpbScheduler.java` (subset k% VM terbaik → min completion time).
- **Metrik**: makespan, energi (6 host selalu menyala sampai Cmax), avg response, utilisasi, DI, throughput, biaya, waktu penjadwalan.
- Validasi: makespan n=100/500/1000 **tepat sama** dengan nilai analitik di README §6.2 (362.45 / 270.95 / 230.90 untuk n=100).

Hasil lengkap: `results/simulation/summary_scalability.csv`  
Diagram: `results/figures/`

## Ringkasan Hasil — Skala 100–1000

| Tasks | k=20% Makespan (s) | k=50% | k=100% | k=20% Energy (kWh) | k=100% Energy |
|------:|-------------------:|------:|-------:|-------------------:|--------------:|
| 100   | 362.45             | 270.95 | 230.90 | 0.0887             | 0.0638        |
| 200   | 754.60             | 538.55 | 450.15 | 0.1843             | 0.1266        |
| 300   | 1035.05            | 722.70 | 592.65 | 0.2561             | 0.1729        |
| 400   | 1323.75            | 919.90 | 782.55 | 0.3273             | 0.2259        |
| 500   | 1630.75            | 1134.70| 925.40 | 0.4034             | 0.2707        |
| 600   | 1942.55            | 1357.65| 1111.70| 0.4802             | 0.3240        |
| 700   | 2342.35            | 1637.55| 1337.95| 0.5790             | 0.3900        |
| 800   | 2637.20            | 1836.15| 1497.10| 0.6522             | 0.4363        |
| 900   | 2983.15            | 2076.00| 1693.00| 0.7379             | 0.4935        |
| 1000  | 3278.25            | 2288.00| 1866.35| 0.8109             | 0.5441        |

## Ringkasan Hasil — Synthetic 1000–10.000

| Tasks | k=20% Makespan (s) | k=50% | k=100% | k=20% Energy (kWh) | k=100% Energy |
|------:|-------------------:|------:|-------:|-------------------:|--------------:|
| 1000  | 3278.25            | 2288.00 | 1866.35 | 0.8109          | 0.5441        |
| 2000  | 6719.95            | 4649.50 | 3755.00 | 1.6630          | 1.0993        |
| 3000  | 9797.15            | 6769.70 | 5455.15 | 2.4235          | 1.6069        |
| 4000  | 13230.40           | 9144.40 | 7385.20 | 3.2731          | 2.1735        |
| 5000  | 16112.45           | 11121.45| 8965.90 | 3.9877          | 2.6431        |
| 6000  | 19328.90           | 13352.05| 10781.05| 4.7836          | 3.1759        |
| 7000  | 22918.40           | 15823.35| 12772.50| 5.6721          | 3.7638        |
| 8000  | 25101.80           | 17342.50| 13983.70| 6.2116          | 4.1203        |
| 9000  | 29328.30           | 20256.95| 16342.55| 7.2565          | 4.8135        |
| 10000 | 32134.50           | 22171.15| 17863.45| 7.9532          | 5.2684        |

## Temuan Utama

1. **Makespan & energi linear terhadap jumlah task** (terlihat jelas di plot log-log). KPB O(n · m log m) tetap praktis: scheduling time ~47 ms untuk 10.000 task.
2. **k=100% (MCT murni) selalu terbaik** untuk makespan, energi, utilisasi, dan biaya pada arsitektur ini (20 VM heterogen, host tetap menyala).
3. **k=20%** mengonsolidasikan ke ~4 VM tercepat → utilisasi ~20%, DI tinggi (~5), makespan ~1.8× lebih buruk vs k=100%.
4. **Trade-off k**: menaikkan k dari 20% → 50% → 100% secara konsisten menurunkan makespan & energi; tidak ada “sweet spot” energi lebih rendah di k kecil karena host idle tetap berkontribusi daya (sesuai analisis README §2).
5. Utilisasi k=100% mendekati 100% pada dataset besar → load balancing sangat baik (DI → 0).

## Diagram

| File | Isi |
|------|-----|
| `results/figures/compare_100_1000.png` | 8 metrik, skala 100–1000 |
| `results/figures/compare_1000_10000.png` | 8 metrik, skala 1000–10.000 |
| `results/figures/bars_100_1000.png` | Bar chart makespan/energi/throughput/util |
| `results/figures/bars_1000_10000.png` | Bar chart skala besar |
| `results/figures/compare_loglog_all.png` | Makespan & energi log-log seluruh skala |

## Cara Menjalankan Ulang

```bash
cd soka-a-5
python3 scripts/run_scalability_experiment.py
```

Script akan (re)generate synthetic dataset jika belum ada, menjalankan semua kombinasi (size × k), menulis CSV, dan menghasilkan PNG.
