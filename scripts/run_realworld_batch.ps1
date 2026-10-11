# Batch real-world Docker runs (butuh docker compose up dulu)
# Dari folder realworld/:
#   docker compose up -d --build
#   powershell -ExecutionPolicy Bypass -File ..\scripts\run_realworld_batch.ps1
#
# Catatan: n besar (5000+) sangat lama di Docker; default hanya official 100-1000
# dan synthetic 1000. Uncomment bagian large bila perlu.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$RW = Join-Path $Root "realworld"
Set-Location $RW

$DS = Join-Path $Root "src\main\resources\dataset"

function Run-RW($file, $k, $repeat=1) {
  Write-Host "=== RealWorld: $(Split-Path $file -Leaf) k=$k ==="
  python kpb_realworld.py --dataset $file --k $k --repeat $repeat --quiet
}

# Official GoCJ 100..1000
foreach ($n in 100,200,300,400,500,600,700,800,900,1000) {
  $f = Join-Path $DS "GoCJ_Dataset_$n.txt"
  if (-not (Test-Path $f)) { continue }
  foreach ($k in 20,50,100) { Run-RW $f $k 1 }
}

# Synthetic 1000 (wajib sesuai permintaan dosen)
$syn1000 = Join-Path $DS "synthetic\Synthetic_GoCJ_1000.txt"
if (Test-Path $syn1000) {
  foreach ($k in 20,50,100) { Run-RW $syn1000 $k 1 }
}

# Synthetic besar — opsional (uncomment jika butuh)
# foreach ($n in 2000,3000,4000,5000,6000,7000,8000,9000,10000) {
#   $f = Join-Path $DS "synthetic\Synthetic_GoCJ_$n.txt"
#   if (-not (Test-Path $f)) { continue }
#   foreach ($k in 20,50,100) { Run-RW $f $k 1 }
# }

Write-Host "Done. Results in realworld/results/"
