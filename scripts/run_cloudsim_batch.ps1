# Batch CloudSim Plus — jalankan di Windows (PowerShell)
# Prasyarat: JDK 11+, folder lib/ sudah ada (jars), project sudah di-compile
# Compile sekali:
#   javac -encoding UTF-8 --release 11 -cp "lib/*" -d target/classes (Get-ChildItem -Recurse src\main\java\*.java).FullName
#
# Usage (dari root soka-a-5):
#   powershell -ExecutionPolicy Bypass -File scripts\run_cloudsim_batch.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$CP = "lib/*;target/classes"
$DS = "src/main/resources/dataset"
$OUT = "results/simulation"
New-Item -ItemType Directory -Force -Path $OUT | Out-Null
New-Item -ItemType Directory -Force -Path target/classes | Out-Null

if (-not (Test-Path "target/classes/project/Experiment.class")) {
  Write-Host "Compiling..."
  $sources = Get-ChildItem -Recurse -Filter *.java src\main\java | ForEach-Object { $_.FullName }
  & javac -encoding UTF-8 --release 11 -cp "lib/*" -d target/classes $sources
}

function Run-One($file, $k) {
  $name = [IO.Path]::GetFileNameWithoutExtension($file)
  Write-Host "=== CloudSim: $name k=$k% ==="
  $log = Join-Path $OUT "log_${name}_k${k}.txt"
  & java -Dlog=error -cp $CP project.Experiment $file $k 2>&1 | Tee-Object -FilePath $log | Select-String "makespan="
}

# Official GoCJ 100..1000
foreach ($n in 100,200,300,400,500,600,700,800,900,1000) {
  $f = Join-Path $DS "GoCJ_Dataset_$n.txt"
  if (-not (Test-Path $f)) { continue }
  foreach ($k in 20,50,100) { Run-One $f $k }
}

# Synthetic 1000..10000
foreach ($n in 1000,2000,3000,4000,5000,6000,7000,8000,9000,10000) {
  $f = Join-Path $DS "synthetic\Synthetic_GoCJ_$n.txt"
  if (-not (Test-Path $f)) { continue }
  foreach ($k in 20,50,100) { Run-One $f $k }
}

Write-Host "Done. See $OUT"
