$rumahReviewInfo = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'review-server.json') -Raw | ConvertFrom-Json
$rumahReviewProcessId = [int]$rumahReviewInfo.pid
$rumahReviewProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$rumahReviewProcessId"
if ($null -eq $rumahReviewProcess) { Write-Output 'Local review helper is already stopped.'; exit 0 }
if ($rumahReviewProcess.CommandLine -notlike '*mobile-20261029*review-server.mjs*') { throw 'The saved PID no longer belongs to this review helper.' }
if ($rumahReviewProcess.ExecutablePath -ne 'C:\Users\bombe\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe') { throw 'Unexpected executable for the review helper.' }
Stop-Process -Id $rumahReviewProcessId -ErrorAction Stop
Write-Output 'Stopped only this task''s local review helper. The public site remains running.'
