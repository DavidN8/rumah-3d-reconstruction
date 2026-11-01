param([switch]$Execute)
$ErrorActionPreference = 'Stop'
$rumahProjectRoot = 'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare'
$rumahDataRoot = Join-Path $rumahProjectRoot 'roomscan-reconstruction\data'
$rumahIphoneRoot = Join-Path $rumahDataRoot '20261027_IPHONE_WIDE'
$rumahSamsungRoot = Join-Path $rumahDataRoot '20261019_095800'
$rumahSharedRuntime = Join-Path $rumahSamsungRoot 'runtime'
$rumahPlanPath = Join-Path $PSScriptRoot 'deletion-plan.json'
$rumahJournalPath = Join-Path $PSScriptRoot 'deletion-journal.jsonl'

function Assert-RumahTarget([string]$LiteralPath) {
    $checkedPath = [IO.Path]::GetFullPath($LiteralPath).TrimEnd('\')
    $allowedPrefix = $rumahProjectRoot + '\'
    if (-not $checkedPath.StartsWith($allowedPrefix,[StringComparison]::OrdinalIgnoreCase)) { throw "Outside project: $checkedPath" }
    foreach ($protectedPath in @($rumahIphoneRoot,$rumahSharedRuntime)) {
        if ($checkedPath.Equals($protectedPath,[StringComparison]::OrdinalIgnoreCase) -or
            $checkedPath.StartsWith($protectedPath+'\',[StringComparison]::OrdinalIgnoreCase) -or
            $protectedPath.StartsWith($checkedPath+'\',[StringComparison]::OrdinalIgnoreCase)) { throw "Protected iPhone path: $checkedPath" }
    }
    $resolvedPath = (Resolve-Path -LiteralPath $checkedPath -ErrorAction Stop).ProviderPath.TrimEnd('\')
    if (-not $resolvedPath.Equals($checkedPath,[StringComparison]::OrdinalIgnoreCase)) { throw "Unexpected path resolution: $resolvedPath" }
    $ancestorPath = $checkedPath
    while ($ancestorPath.Length -ge $rumahProjectRoot.Length) {
        $pathItem = Get-Item -LiteralPath $ancestorPath -Force
        if (($pathItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Reparse point in target ancestry: $ancestorPath" }
        if ($ancestorPath.Equals($rumahProjectRoot,[StringComparison]::OrdinalIgnoreCase)) { break }
        $ancestorPath = [IO.Path]::GetDirectoryName($ancestorPath)
    }
    return $checkedPath
}

if (-not $Execute) {
    if (Test-Path -LiteralPath $rumahPlanPath) { throw 'A plan already exists; inspect it before replacing.' }
    $plannedTargets = @([pscustomobject]@{path=(Join-Path $rumahDataRoot '20261019_VID_2445');reason='Retired Nikon source footage, datasets, training and exports'})
    foreach ($childItem in Get-ChildItem -LiteralPath $rumahSamsungRoot -Force) {
        if ($childItem.Name -eq 'runtime') { continue }
        $plannedTargets += [pscustomobject]@{path=$childItem.FullName;reason='Retired Samsung data; shared runtime excluded'}
    }
    foreach ($relativePath in @('artifacts\model-release-2026-10-19','artifacts\model-release-2026-10-19-v2','artifacts\single-model-release','artifacts\portable-smoke','artifacts\single-package-smoke','.roomscan-viewer\site\high-quality')) {
        $plannedTargets += [pscustomobject]@{path=(Join-Path $rumahProjectRoot $relativePath);reason='Reviewed legacy Samsung export package, test copy or prepared viewer cache'}
    }
    foreach ($target in $plannedTargets) { $target.path = Assert-RumahTarget $target.path }
    $retiredRecords = Join-Path $PSScriptRoot 'retired-release-records'
    New-Item -ItemType Directory -Path $retiredRecords -Force | Out-Null
    foreach ($folderName in @('model-release-2026-10-19','model-release-2026-10-19-v2','single-model-release')) {
        $recordSource = Join-Path $rumahProjectRoot ('artifacts\'+$folderName+'\package-manifest.json')
        Copy-Item -LiteralPath $recordSource -Destination (Join-Path $retiredRecords ($folderName+'.json'))
    }
    $plan = [pscustomobject]@{date='2026-10-31';authorization='User requested deletion of unused Nikon and Samsung work, keeping iPhone; asked agent to review other project exports';projectRoot=$rumahProjectRoot;protected=@($rumahIphoneRoot,$rumahSharedRuntime);targets=$plannedTargets;sharedRuntimeReason='Current iPhone scripts 20_component_recovery.py and 14_metric_bridge.py reference the Samsung runtime at its existing path'}
    $plan | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $rumahPlanPath -Encoding utf8
    Write-Output ($plan | ConvertTo-Json -Depth 6)
    exit 0
}

$plan = Get-Content -LiteralPath $rumahPlanPath -Raw | ConvertFrom-Json
if ($plan.projectRoot -ne $rumahProjectRoot) { throw 'Unexpected plan root' }
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'protected-before.json'))) { throw 'Missing protected iPhone snapshot' }
if (Test-Path -LiteralPath $rumahJournalPath) { throw 'Cleanup already started; inspect journal instead of rerunning blindly' }
foreach ($target in $plan.targets) { $null = Assert-RumahTarget $target.path }
$spaceBefore = (Get-PSDrive -Name C).Free
@{event='start';time=(Get-Date -Format o);freeBytes=$spaceBefore;targetCount=$plan.targets.Count} | ConvertTo-Json -Compress | Add-Content -LiteralPath $rumahJournalPath
$completedCount = 0
foreach ($target in $plan.targets) {
    $checkedPath = Assert-RumahTarget $target.path
    @{event='deleting';time=(Get-Date -Format o);path=$checkedPath;reason=$target.reason} | ConvertTo-Json -Compress | Add-Content -LiteralPath $rumahJournalPath
    Write-Output ("Removing {0}/{1}: {2}" -f ($completedCount+1),$plan.targets.Count,$checkedPath)
    Remove-Item -LiteralPath $checkedPath -Recurse -Force -ErrorAction Stop
    if (Test-Path -LiteralPath $checkedPath) { throw "Removal incomplete: $checkedPath" }
    $completedCount++
    @{event='removed';time=(Get-Date -Format o);path=$checkedPath;freeBytes=(Get-PSDrive -Name C).Free} | ConvertTo-Json -Compress | Add-Content -LiteralPath $rumahJournalPath
}
$spaceAfter = (Get-PSDrive -Name C).Free
$summary = @{event='complete';time=(Get-Date -Format o);removedTargets=$completedCount;freeBytesBefore=$spaceBefore;freeBytesAfter=$spaceAfter;freeBytesChange=($spaceAfter-$spaceBefore)}
$summary | ConvertTo-Json -Compress | Add-Content -LiteralPath $rumahJournalPath
Write-Output ($summary | ConvertTo-Json)
