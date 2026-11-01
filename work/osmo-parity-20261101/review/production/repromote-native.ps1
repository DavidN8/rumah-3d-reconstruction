$ErrorActionPreference = 'Stop'
$retryWorkspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../../..'))
$retryPython = 'C:/Users/bombe/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$retryRemote = Join-Path $retryWorkspace 'work/hosting/remote.py'
$retryDirectory = Join-Path $PSScriptRoot 'deployment'
$retryStage = '/var/lib/vz/rumah-deploy/20261031-osmo-clean-v1'
$retryHash = 'c5a89099aff9bd238e015b405112f20c07a585430624bbb22340c9dbf47c4fba'
$retryRollbackHash = 'bfa7791f7fb46ec2422e453b1389dbd7febdd6a5be87005cf41370d7633e9fb2'
function Invoke-RetryRemote([string[]]$RemoteArguments) {
    & $retryPython $retryRemote @RemoteArguments
    if ($LASTEXITCODE -ne 0) { throw 'Repromotion step failed; inspect receipts and current release before retrying.' }
}
foreach ($retryScript in @(@('repromote-native.sh',$retryHash),@('rollback-native-retry.sh',$retryRollbackHash))) {
    $retryLocal = Join-Path $retryDirectory $retryScript[0]
    if ((Get-FileHash -LiteralPath $retryLocal -Algorithm SHA256).Hash.ToLowerInvariant() -ne $retryScript[1]) { throw 'Reviewed retry script changed.' }
    $retryTarget = $retryStage + '/' + $retryScript[0]
    $retryPrepare = "test ! -L '{0}' && {{ test -f '{0}' || install -m 0600 /dev/null '{0}'; }}" -f $retryTarget
    Invoke-RetryRemote @('--command',$retryPrepare,'--limit','30')
    Invoke-RetryRemote @('--put',$retryLocal,$retryTarget,'--limit','60')
}
$retryRun = "printf '%s\n' '{0}  {1}/repromote-native.sh' | sha256sum -c - && timeout -s TERM 180 bash '{1}/repromote-native.sh'" -f $retryHash,$retryStage
Invoke-RetryRemote @('--command',$retryRun,'--limit','195')
& $retryPython (Join-Path $PSScriptRoot 'verify-public-native.py')
if ($LASTEXITCODE -ne 0) {
    $retryUndo = "printf '%s\n' '{0}  {1}/rollback-native-retry.sh' | sha256sum -c - && timeout -s TERM 45 bash '{1}/rollback-native-retry.sh'" -f $retryRollbackHash,$retryStage
    Invoke-RetryRemote @('--command',$retryUndo,'--limit','60')
    throw 'Public retry verification failed; retained previous release restored.'
}
Write-Output 'Existing reviewed release re-promoted and public checks passed; no models were re-uploaded.'
