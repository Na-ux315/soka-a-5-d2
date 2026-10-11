#!/usr/bin/env bash
# Batch CloudSim Plus runs for all GoCJ official (100-1000) and synthetic (1000-10000).
# Usage: bash scripts/run_cloudsim_batch.sh
# Requires: JDK 11+, jars in lib/, compiled classes in target/classes
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CP="lib/*:target/classes"
DS=src/main/resources/dataset
OUT=results/simulation
mkdir -p "$OUT" target/classes

# Compile if needed
if [ ! -f target/classes/project/Experiment.class ]; then
  echo "Compiling..."
  javac -encoding UTF-8 --release 11 -cp "lib/*" -d target/classes $(find src/main/java -name "*.java")
fi

run_one() {
  local file="$1"
  local k="$2"
  local name
  name="$(basename "$file" .txt)"
  echo "=== CloudSim: $name k=$k% ==="
  java -Dlog=error -cp "$CP" project.Experiment "$file" "$k" \
    > "$OUT/log_${name}_k${k}.txt" 2>&1 || {
      echo "FAILED: $name k=$k"
      tail -20 "$OUT/log_${name}_k${k}.txt"
      return 1
    }
  # Extract key metrics from log
  grep -E "makespan=|scheduler=|tasks=" "$OUT/log_${name}_k${k}.txt" | head -5
}

# Official GoCJ 100..1000
for n in 100 200 300 400 500 600 700 800 900 1000; do
  f="$DS/GoCJ_Dataset_${n}.txt"
  [ -f "$f" ] || continue
  for k in 20 50 100; do
    run_one "$f" "$k"
  done
done

# Synthetic 1000..10000 (CloudSim can be slow for large n; still run)
for n in 1000 2000 3000 4000 5000 6000 7000 8000 9000 10000; do
  f="$DS/synthetic/Synthetic_GoCJ_${n}.txt"
  [ -f "$f" ] || continue
  for k in 20 50 100; do
    run_one "$f" "$k"
  done
done

echo "Done. Logs and cloudlets CSV in $OUT/"
ls -la "$OUT"/cloudlets_*.csv 2>/dev/null | wc -l
echo "summary.csv:"
tail -5 "$OUT/summary.csv" 2>/dev/null || true
