[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$failures = [System.Collections.Generic.List[string]]::new()

function Add-Failure {
    param([string]$Message)
    $failures.Add($Message)
}

function Relative-Path {
    param([string]$Path)
    return [IO.Path]::GetRelativePath($repositoryRoot, $Path)
}

$chapters = Get-ChildItem -LiteralPath $repositoryRoot -Directory |
    Where-Object Name -Match '^\d{2}-' |
    Sort-Object Name

if ($chapters.Count -ne 16) {
    Add-Failure "Expected 16 numbered chapter directories; found $($chapters.Count)."
}

foreach ($chapter in $chapters) {
    foreach ($name in @("lesson.md", "exercises.md", "test.md")) {
        $requiredFile = Join-Path $chapter.FullName $name
        if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
            Add-Failure "Missing $(Relative-Path $requiredFile)."
        }
    }

    $lesson = Join-Path $chapter.FullName "lesson.md"
    $exercises = Join-Path $chapter.FullName "exercises.md"
    $test = Join-Path $chapter.FullName "test.md"
    if (-not (Test-Path $lesson) -or -not (Test-Path $exercises) -or -not (Test-Path $test)) {
        continue
    }

    $lessonText = Get-Content -LiteralPath $lesson -Raw
    if ($lessonText -notmatch '(?m)^## Abbreviations\s*$') {
        Add-Failure "$(Relative-Path $lesson) has no Abbreviations section."
    }
    if ($lessonText -notmatch '\*\*Next:\*\*') {
        Add-Failure "$(Relative-Path $lesson) has no next-step navigation."
    }

    $exerciseText = Get-Content -LiteralPath $exercises -Raw
    $exerciseCount = ([regex]::Matches($exerciseText, '(?m)^## Exercise ')).Count
    $verifyCount = ([regex]::Matches($exerciseText, '(?m)^\*\*Verify')).Count
    if ($exerciseCount -lt 6) {
        Add-Failure "$(Relative-Path $exercises) has only $exerciseCount exercises."
    }
    if ($verifyCount -lt ($exerciseCount - 1)) {
        Add-Failure "$(Relative-Path $exercises) has $exerciseCount exercises but only $verifyCount verification blocks."
    }

    $testText = Get-Content -LiteralPath $test -Raw
    $questionCount = ([regex]::Matches($testText, '(?m)^\*\*Q\d+\.\*\*')).Count
    if ($questionCount -ne 15) {
        Add-Failure "$(Relative-Path $test) has $questionCount questions; expected 15."
    }
    if ($testText -notmatch '<summary><b>Answer key</b></summary>') {
        Add-Failure "$(Relative-Path $test) has no collapsible answer key."
    }
}

$markdownFiles = Get-ChildItem -LiteralPath $repositoryRoot -Recurse -File -Filter "*.md" |
    Where-Object FullName -NotMatch '[\\/](\.git|\.terraform|\.tmp-tools|node_modules)[\\/]'

foreach ($file in $markdownFiles) {
    $text = Get-Content -LiteralPath $file.FullName -Raw
    $fenceCount = ([regex]::Matches($text, '```')).Count
    if ($fenceCount % 2 -ne 0) {
        Add-Failure "$(Relative-Path $file.FullName) has an odd number of code fences."
    }

    foreach ($match in [regex]::Matches($text, '\[[^\]]*\]\(([^)]+)\)')) {
        $rawTarget = $match.Groups[1].Value.Trim()
        if (
            $rawTarget -match '^(https?://|mailto:|#)' -or
            $rawTarget -match '^\{\{' -or
            [string]::IsNullOrWhiteSpace($rawTarget)
        ) {
            continue
        }

        $target = $rawTarget.Split("#")[0].Trim("<>")
        $target = [Uri]::UnescapeDataString($target)
        $resolved = Join-Path $file.DirectoryName $target
        if (-not (Test-Path -LiteralPath $resolved)) {
            Add-Failure "$(Relative-Path $file.FullName) links to missing target '$rawTarget'."
        }
    }

    if ($text -match '(?m)^(<<<<<<<|=======|>>>>>>>)') {
        Add-Failure "$(Relative-Path $file.FullName) contains an unresolved conflict marker."
    }
}

$requiredLabFiles = @(
    "labs/visits-platform/app/app.py",
    "labs/visits-platform/app/worker.py",
    "labs/visits-platform/compose.yaml",
    "labs/visits-platform/Dockerfile",
    "labs/visits-platform/.github/workflows/ci.yml",
    "labs/visits-platform/Jenkinsfile",
    "labs/visits-platform/.gitlab-ci.yml",
    "labs/visits-platform/k8s/platform.yaml",
    "labs/visits-platform/helm/visits/Chart.yaml",
    "labs/visits-platform/infra/terraform/main.tf",
    "labs/visits-platform/infra/ansible/site.yml",
    "labs/visits-platform/observability/prometheus/rules.yml"
)

foreach ($relativeFile in $requiredLabFiles) {
    $labFile = Join-Path $repositoryRoot $relativeFile
    if (-not (Test-Path -LiteralPath $labFile -PathType Leaf)) {
        Add-Failure "Missing required runnable lab asset: $relativeFile."
    }
}

$jsonFiles = Get-ChildItem -LiteralPath $repositoryRoot -Recurse -File -Filter "*.json" |
    Where-Object FullName -NotMatch '[\\/](\.git|\.terraform|\.tmp-tools|node_modules)[\\/]'
foreach ($jsonFile in $jsonFiles) {
    try {
        Get-Content -LiteralPath $jsonFile.FullName -Raw | ConvertFrom-Json | Out-Null
    }
    catch {
        Add-Failure "$(Relative-Path $jsonFile.FullName) is not valid JSON: $($_.Exception.Message)"
    }
}

if ($failures.Count -gt 0) {
    Write-Host "Course validation failed with $($failures.Count) problem(s):" -ForegroundColor Red
    foreach ($failure in $failures) {
        Write-Host " - $failure" -ForegroundColor Red
    }
    exit 1
}

Write-Host "Course validation passed: 16 chapters, $($markdownFiles.Count) Markdown files, runnable lab assets, links, fences, and JSON." -ForegroundColor Green
