# Put the reader's original Youdao English-Chinese dictionary back.
# Usage (reader connected over USB in file-transfer mode):
#   powershell -ExecutionPolicy Bypass -File restore_system_dict.ps1
# To push the enriched version again instead, pass:  -Source system-dict-new
param([string]$Source = 'system-dict-backup\dict')

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$srcDir = Join-Path $here $Source
$shell = New-Object -ComObject Shell.Application
$dev = $shell.Namespace(17).Items() | Where-Object { $_.Name -eq 'Ocean 4 Turbo' }
if (-not $dev) { Write-Host 'Reader not connected'; exit 1 }
$root = $dev.GetFolder.Items() | Select-Object -First 1
$dest = ($root.GetFolder.Items() | Where-Object { $_.Name -eq 'dict' }).GetFolder
$trash = Join-Path $here ('system-dict-replaced\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force $trash | Out-Null

foreach ($fn in 'yddict.idx', 'e2170331.ydd') {
  $src = Join-Path $srcDir $fn
  $expected = (Get-Item -LiteralPath $src).Length
  $item = $dest.Items() | Where-Object { $_.Name -eq $fn }
  if ($item) {
    # MTP copy will not overwrite, so move the current file off the device first
    $shell.Namespace($trash).MoveHere($item, 4 + 16 + 1024)
    $deadline = (Get-Date).AddMinutes(3)
    do { Start-Sleep -Seconds 2; $still = $dest.Items() | Where-Object { $_.Name -eq $fn } } while ($still -and (Get-Date) -lt $deadline)
    if ($still) { Write-Host "Could not remove $fn from the reader"; exit 2 }
  }
  $dest.CopyHere($src, 4 + 16 + 1024)
  $deadline = (Get-Date).AddMinutes(4)
  do {
    Start-Sleep -Seconds 2
    $f = $dest.Items() | Where-Object { $_.Name -eq $fn }
    $sz = if ($f) { [int64]$f.ExtendedProperty('System.Size') } else { 0 }
  } while ($sz -ne $expected -and (Get-Date) -lt $deadline)
  Write-Host ("{0}: {1}" -f $fn, $(if ($sz -eq $expected) { 'OK' } else { "FAILED (size $sz, expected $expected)" }))
}
Write-Host 'Done. Restart the reader app (or reboot the reader) to load the dictionary.'
