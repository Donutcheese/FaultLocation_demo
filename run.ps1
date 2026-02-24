param(
  [Parameter(Mandatory=$false)]
  [string]$Cmd = "demo"
)

$ErrorActionPreference = "Stop"

$version = "3.51.2.0"
$jarName = "sqlite-jdbc-$version.jar"
$jarUrl = "https://repo1.maven.org/maven2/org/xerial/sqlite-jdbc/$version/$jarName"

$depsDir = Join-Path $PSScriptRoot "deps"
$outDir  = Join-Path $PSScriptRoot "out"

if (!(Test-Path $depsDir)) { New-Item -ItemType Directory -Path $depsDir | Out-Null }
if (!(Test-Path $outDir))  { New-Item -ItemType Directory -Path $outDir  | Out-Null }

$primaryJarPath = Join-Path $depsDir $jarName
$jarPath = $primaryJarPath

function Get-FileSize([string]$p) {
  if (!(Test-Path $p)) { return 0 }
  return (Get-Item $p).Length
}

# 如果之前下载中断导致 0 字节文件被占用，使用一个新的文件名下载，避免锁冲突
if ((Test-Path $primaryJarPath) -and ((Get-FileSize $primaryJarPath) -lt 1024)) {
  $jarPath = Join-Path $depsDir ("sqlite-jdbc-$version-" + (Get-Date -Format "yyyyMMddHHmmss") + ".jar")
}

if (!(Test-Path $jarPath) -or ((Get-FileSize $jarPath) -lt 1024)) {
  Write-Host "Downloading SQLite JDBC: $jarName"
  $tmp = "$jarPath.tmp"
  if (Test-Path $tmp) { Remove-Item -Force $tmp }

  # 使用 curl.exe（Windows 自带）更稳定，并带重试
  & curl.exe -L --fail --retry 3 --retry-delay 2 -o $tmp $jarUrl
  Move-Item -Force $tmp $jarPath
}

$srcDir = Join-Path $PSScriptRoot "src"
if (!(Test-Path $srcDir)) { throw "Missing source directory: $srcDir" }

# 收集 src 目录下所有 .java 源文件，一次性编译，保证模块化拆分后的多个类都能被找到
$sources = Get-ChildItem -Path $srcDir -Filter *.java | ForEach-Object { $_.FullName }
if ($sources.Count -eq 0) { throw "No .java files found in $srcDir" }

Write-Host "Compiling..."
javac -encoding UTF-8 -cp $jarPath -d $outDir $sources

Write-Host "Running: $Cmd"
java -cp "$outDir;$jarPath" Main $Cmd

