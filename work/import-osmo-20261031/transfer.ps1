$ErrorActionPreference = 'Stop'
$osmoSourceRoot = 'E:\DCIM\CAM_001'
$osmoProjectRoot = 'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare'
$osmoDataRoot = Join-Path $osmoProjectRoot 'roomscan-reconstruction\data'
$osmoCaptureRoot = Join-Path $osmoDataRoot '20261031_OSMO360'
$osmoDestinationRoot = Join-Path $osmoCaptureRoot 'originals'
$osmoFileNames = @('CAM_20261031005909_0004_D.OSV','CAM_20261031005909_0004_D.LRF')
$osmoReceiptPath = Join-Path $PSScriptRoot 'transfer-receipt.json'
$osmoJournalPath = Join-Path $PSScriptRoot 'transfer-journal.jsonl'

function Assert-OsmoPath([string]$LiteralPath,[string]$ExpectedRoot) {
    $checkedPath = [IO.Path]::GetFullPath($LiteralPath)
    $checkedRoot = [IO.Path]::GetFullPath($ExpectedRoot).TrimEnd('\')
    if (-not $checkedPath.StartsWith($checkedRoot+'\',[StringComparison]::OrdinalIgnoreCase)) { throw "Path escapes intended root: $checkedPath" }
    return $checkedPath
}
function Write-OsmoEvent([string]$Event,[string]$Name) {
    @{event=$Event;file=$Name;time=(Get-Date -Format o)} | ConvertTo-Json -Compress | Add-Content -LiteralPath $osmoJournalPath
    Write-Output "$Event : $Name"
}

if (Test-Path -LiteralPath $osmoReceiptPath) { throw 'Transfer already recorded; inspect receipt before rerunning.' }
if (Test-Path -LiteralPath $osmoJournalPath) { throw 'A prior transfer started; inspect its journal before continuing.' }
if ((Get-Volume -DriveLetter E).FileSystemLabel -ne 'Osmo360II') { throw 'The E: drive no longer matches the inspected camera.' }
if ((Resolve-Path -LiteralPath $osmoSourceRoot).ProviderPath -ne $osmoSourceRoot) { throw 'Unexpected source directory resolution.' }
if ((Resolve-Path -LiteralPath $osmoDataRoot).ProviderPath -ne $osmoDataRoot) { throw 'Unexpected project directory resolution.' }
foreach ($rootPath in @($osmoSourceRoot,$osmoProjectRoot,$osmoDataRoot)) {
    if (((Get-Item -LiteralPath $rootPath -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Unexpected reparse point: $rootPath" }
}
if (Test-Path -LiteralPath $osmoCaptureRoot) { throw 'Capture folder already exists; refusing to overwrite it.' }
$transferItems = @()
foreach ($fileName in $osmoFileNames) {
    $sourcePath = Assert-OsmoPath (Join-Path $osmoSourceRoot $fileName) $osmoSourceRoot
    $destinationPath = Assert-OsmoPath (Join-Path $osmoDestinationRoot $fileName) $osmoCaptureRoot
    $sourceItem = Get-Item -LiteralPath $sourcePath -Force
    if ($sourceItem.PSIsContainer -or (($sourceItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) { throw "Expected an ordinary source file: $sourcePath" }
    $transferItems += [pscustomobject]@{name=$fileName;source=$sourcePath;destination=$destinationPath;bytes=$sourceItem.Length;sourceModifiedUtc=$sourceItem.LastWriteTimeUtc.ToString('o');sha256=$null;sourceRemoved=$false}
}
$transferTotal = ($transferItems | Measure-Object -Property bytes -Sum).Sum
if ((Get-PSDrive C).Free -lt ($transferTotal+64MB)) { throw 'Insufficient destination free space.' }
New-Item -ItemType Directory -Path $osmoDestinationRoot -ErrorAction Stop | Out-Null
if ((Resolve-Path -LiteralPath $osmoDestinationRoot).ProviderPath -ne $osmoDestinationRoot) { throw 'Destination resolution changed.' }

foreach ($transferItem in $transferItems) {
    $temporaryPath = Assert-OsmoPath ($transferItem.destination+'.copying') $osmoCaptureRoot
    Write-OsmoEvent 'Copying' $transferItem.name
    Copy-Item -LiteralPath $transferItem.source -Destination $temporaryPath -ErrorAction Stop
    Write-OsmoEvent 'Verifying source and copy' $transferItem.name
    $sourceHash = (Get-FileHash -LiteralPath $transferItem.source -Algorithm SHA256).Hash.ToLowerInvariant()
    $copyHash = (Get-FileHash -LiteralPath $temporaryPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $currentSource = Get-Item -LiteralPath $transferItem.source
    $copyItem = Get-Item -LiteralPath $temporaryPath
    if ($sourceHash -ne $copyHash -or $copyItem.Length -ne $transferItem.bytes -or
        $currentSource.Length -ne $transferItem.bytes -or
        $currentSource.LastWriteTimeUtc.ToString('o') -ne $transferItem.sourceModifiedUtc) { throw "Transfer verification failed; original retained: $($transferItem.name)" }
    Rename-Item -LiteralPath $temporaryPath -NewName $transferItem.name -ErrorAction Stop
    $transferItem.sha256 = $copyHash
    Write-OsmoEvent 'Verified' $transferItem.name
}

# Commit the move only after both complete destination files pass SHA256 checks.
$receipt = [pscustomobject]@{date='2026-10-31';status='copies_verified_sources_present';sourceRoot=$osmoSourceRoot;captureRoot=$osmoCaptureRoot;totalBytes=$transferTotal;files=$transferItems;formatReference='https://repair.dji.com/help/content?customId=01700006849&lang=en&paperDocType=ARTICLE&re=US&spaceId=17';originalFormat='OSV';proxyFormat='LRF'}
$receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $osmoReceiptPath -Encoding utf8
$receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $osmoCaptureRoot 'capture-manifest.json') -Encoding utf8
foreach ($transferItem in $transferItems) {
    $checkedSource = Assert-OsmoPath $transferItem.source $osmoSourceRoot
    $checkedDestination = Assert-OsmoPath $transferItem.destination $osmoCaptureRoot
    $currentSource = Get-Item -LiteralPath $checkedSource
    if ($currentSource.Length -ne $transferItem.bytes -or $currentSource.LastWriteTimeUtc.ToString('o') -ne $transferItem.sourceModifiedUtc) { throw "Source changed; left on camera: $($transferItem.name)" }
    if (-not (Test-Path -LiteralPath $checkedDestination -PathType Leaf)) { throw "Destination is missing; original retained: $($transferItem.name)" }
    Write-OsmoEvent 'Removing verified source from camera' $transferItem.name
    Remove-Item -LiteralPath $checkedSource -Force -ErrorAction Stop
    if (Test-Path -LiteralPath $checkedSource) { throw "Source removal failed: $checkedSource" }
    $transferItem.sourceRemoved = $true
    $receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $osmoReceiptPath -Encoding utf8
}
$receipt.status = 'moved_and_verified'
$receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $osmoReceiptPath -Encoding utf8
$receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $osmoCaptureRoot 'capture-manifest.json') -Encoding utf8
Write-Output ($receipt | ConvertTo-Json -Depth 6)
