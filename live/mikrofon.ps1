# The live service's images: a change is tried as a test, and only an image of a clean origin/main goes live.
#   .\mikrofon.ps1 test [-Novo]   build this working tree and run it beside the live service (-Novo: everything fetched
#                                 afresh, the newest yt-dlp among it). From the main clone on main: mikrofon:test at
#                                 http://127.0.0.1:8001/; from a worktree: mikrofon:test-<branch> on a port of its own.
#   .\mikrofon.ps1 uzivo          mikrofon:test goes live (mikrofon:uzivo), if it was built from a clean origin/main
#                                 (-Ipak: whatever it is). While someone speaks it waits for the turn to end (-Cekaj
#                                 minutes at most, 10 by default; -Odmah: at once). If the new one doesn't answer
#                                 within 90 s, the one before goes live again. The page goes on during the restart.
#   .\mikrofon.ps1 nazad          the image that was live before goes live again (at once)
#   .\mikrofon.ps1 stanje         what runs, and which image is which commit
#   .\mikrofon.ps1 logovi [-Test] the live service's log (or this tree's test's), followed
#   .\mikrofon.ps1 ocisti         remove images nothing uses: untagged ones, and tests of worktrees no container runs
param(
    [Parameter(Position = 0)][ValidateSet("test", "uzivo", "nazad", "stanje", "logovi", "ocisti")][string]$Korak = "stanje",
    [switch]$Novo,
    [switch]$Odmah,
    [switch]$Ipak,
    [switch]$Test,
    [int]$Cekaj = 10
)
# Not "Stop": Windows PowerShell takes docker's progress on stderr for an error. Exit codes are checked (Assert-Ok).
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

function Assert-Ok([string]$What) {
    if ($LASTEXITCODE -ne 0) { throw "$What nije uspelo (izlaz $LASTEXITCODE)." }
}

function Get-ImageId([string]$Tag) {
    $id = docker images -q $Tag
    if ($id) { return ($id | Select-Object -First 1).Trim() }
    return ""
}

function Get-Label([string]$Tag, [string]$Name) {
    # All labels as JSON: Windows PowerShell drops the quotes a Go template's `index` would need.
    $json = docker image inspect $Tag --format "{{json .Config.Labels}}" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $json -or "$json" -eq "null") { return "" }
    $v = ("$json" | ConvertFrom-Json)."zailiprotiv.$Name"
    if ($v) { return "$v".Trim() }
    return ""
}

# This tree: its commit, its branch, whether it has changes not committed; and which test is its own.
$Tree = @{}
$Tree.Sha = (git rev-parse --short HEAD).Trim()
$Tree.Branch = (git rev-parse --abbrev-ref HEAD).Trim()
$Tree.Clean = if (git status --porcelain) { "ne" } else { "da" }
$Tree.Main = ((git worktree list --porcelain | Select-Object -First 1) -replace "^worktree ", "").Trim()
$here = (git rev-parse --show-toplevel).Trim()
$Tree.IsMain = ($here -eq $Tree.Main) -and ($Tree.Branch -eq "main")
if ($Tree.IsMain) {
    $Tree.Image, $Tree.Project, $Tree.Port, $Tree.Volume = "mikrofon:test", "mikrofon-test", 8001, "mikrofon-test-podaci"
} else {
    $slug = (($Tree.Branch -split "/")[-1].ToLower() -replace "[^a-z0-9-]", "-").Trim("-")
    if ($slug.Length -gt 30) { $slug = $slug.Substring(0, 30).Trim("-") }
    $sum = 0; foreach ($c in $slug.ToCharArray()) { $sum = ($sum * 31 + [int]$c) % 9973 }
    $Tree.Image, $Tree.Project = "mikrofon:test-$slug", "mikrofon-test-$slug"
    $Tree.Port, $Tree.Volume = (8002 + $sum % 90), "mikrofon-test-$slug-podaci"
}
$env:TEST_IMAGE, $env:TEST_PROJEKAT, $env:TEST_PORT, $env:TEST_PODACI = $Tree.Image, $Tree.Project, "$($Tree.Port)", $Tree.Volume
$env:VERZIJA, $env:GRANA, $env:CISTO = $Tree.Sha, $Tree.Branch, $Tree.Clean

# A worktree has no .env of its own (never committed): the main clone's is used. Not .tunnel.env: a test has no tunnel.
if (-not (Test-Path .env) -and (Test-Path (Join-Path $Tree.Main "live\.env"))) {
    Copy-Item (Join-Path $Tree.Main "live\.env") .env
    Write-Host "Uzet .env iz glavnog klona."
}
# Whisper's model, shared by the live service and every test, fetched once.
docker volume inspect mikrofon-whisper *> $null
if ($LASTEXITCODE -ne 0) { docker volume create mikrofon-whisper | Out-Null }

# Until the page answers on its port (and, given a commit, says it runs that one): $true, or $false after $Seconds.
function Wait-Page([int]$Port, [string]$Version, [int]$Seconds = 90) {
    $until = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $until) {
        try {
            $s = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/stanje.json" -TimeoutSec 4
            if (-not $Version -or $s.verzija -eq $Version) { return $true }
        } catch {}
        Start-Sleep -Seconds 2
    }
    return $false
}

# The restart in a gap (20 Nov 2026): the edge keeps the page's last answer and the service takes up the turn on,
# so a restart mid-speech shows nothing wrong; still, between turns it misses not even a few frames of anyone's.
function Wait-Gap([int]$Minutes) {
    $until = (Get-Date).AddMinutes($Minutes)
    $said = $false
    while ((Get-Date) -lt $until) {
        try { $s = Invoke-RestMethod -Uri http://127.0.0.1:8000/stanje.json -TimeoutSec 5 } catch { return }
        if ($s.stanje -ne "govori") { return }
        if (-not $said) { Write-Host "Govori $($s.sada.ime): cekam kraj govora (najvise $Minutes min; -Odmah za odmah)..."; $said = $true }
        Start-Sleep -Seconds 3
    }
    Write-Host "Govor traje duze od $Minutes min: menjam sada (stranica i govor se nastavljaju)."
}

# Put an image live, wait until it answers, and if it doesn't, put the one before back.
function Set-Live([string]$Version) {
    docker compose up -d; Assert-Ok "Pokretanje uzivo"
    if (Wait-Page 8000 $Version 90) { return }
    if (-not (Get-ImageId "mikrofon:prethodni")) { throw "Novi image ne odgovara posle 90 s, a prethodnog nema: pogledaj .\mikrofon.ps1 logovi." }
    docker tag mikrofon:prethodni mikrofon:uzivo; Assert-Ok "Vracanje prethodnog"
    docker compose up -d; Assert-Ok "Pokretanje prethodnog"
    throw "Novi image ($Version) ne odgovara posle 90 s: vracen je prethodni. Pogledaj logove testa."
}

function Show-Image([string]$Tag) {
    if (-not (Get-ImageId $Tag)) { return }
    $v, $b, $c = (Get-Label $Tag "verzija"), (Get-Label $Tag "grana"), (Get-Label $Tag "cisto")
    $made = "$(docker image inspect $Tag --format '{{.Created}}')"
    $note = if ($v) { "$v ($b$(if ($c -eq 'ne') { ', necisto' }))" } else { "bez oznake verzije" }
    Write-Host ("  {0,-34} {1}  napravljen {2}" -f $Tag, $note, ($made.Substring(0, [Math]::Min(16, $made.Length)) -replace "T", " "))
}

switch ($Korak) {
    "test" {
        if ($Novo) { docker compose -f docker-compose.test.yml build --pull --no-cache; Assert-Ok "Build" }
        docker compose -f docker-compose.test.yml up -d --build; Assert-Ok "Pokretanje testa"
        $ok = Wait-Page $Tree.Port $Tree.Sha 90
        $dirty = if ($Tree.Clean -eq "ne") { ", sa izmenama koje nisu commit-ovane" } else { "" }
        Write-Host "Test $($Tree.Image): $($Tree.Sha) sa grane $($Tree.Branch)$dirty"
        if ($ok) { Write-Host "Radi na http://127.0.0.1:$($Tree.Port)/  (logovi: .\mikrofon.ps1 logovi -Test)" }
        else { Write-Host "Ne odgovara posle 90 s: .\mikrofon.ps1 logovi -Test" }
    }
    "uzivo" {
        if (-not $Tree.IsMain) { throw "Uzivo se pusta iz glavnog klona ($($Tree.Main)), na grani main." }
        $test = Get-ImageId "mikrofon:test"
        if (-not $test) { throw "Nema mikrofon:test: prvo .\mikrofon.ps1 test." }
        if (-not (Test-Path .tunnel.env)) { throw "Nema .tunnel.env (TUNNEL_TOKEN=... iz Cloudflare-a)." }
        git fetch -q origin
        $want = (git rev-parse --short origin/main).Trim()
        $v, $b, $c = (Get-Label "mikrofon:test" "verzija"), (Get-Label "mikrofon:test" "grana"), (Get-Label "mikrofon:test" "cisto")
        if (-not $Ipak -and ($v -ne $want -or $b -ne "main" -or $c -ne "da")) {
            $what = if ($v) { "$v sa grane $b$(if ($c -eq 'ne') { ', sa izmenama koje nisu commit-ovane' })" } else { "bez oznake verzije" }
            throw "mikrofon:test je $what, a origin/main je $want. Prvo: git pull; .\mikrofon.ps1 test (ili -Ipak)."
        }
        $live = Get-ImageId "mikrofon:uzivo"
        if ($live -eq $test) { Write-Host "Testirani image je vec uzivo." }
        else {
            if (-not $Odmah) { Wait-Gap $Cekaj }
            if ($live) { docker tag mikrofon:uzivo mikrofon:prethodni; Assert-Ok "Cuvanje prethodnog" }
            docker tag mikrofon:test mikrofon:uzivo; Assert-Ok "Oznacavanje"
        }
        Set-Live $v
        # The test reads the same broadcast with Whisper too; once its image is live it only takes the cores.
        docker compose -f docker-compose.test.yml stop
        Write-Host "Uzivo radi $v (https://mikrofon.zailiprotiv.rs/stanje.json kaze `"verzija`"); test zaustavljen."
    }
    "nazad" {
        if (-not (Get-ImageId "mikrofon:prethodni")) { throw "Nema mikrofon:prethodni." }
        docker tag mikrofon:prethodni mikrofon:uzivo; Assert-Ok "Oznacavanje"
        docker compose up -d; Assert-Ok "Pokretanje uzivo"
        if (Wait-Page 8000 "" 90) { Write-Host "Uzivo ponovo radi prethodni image ($(Get-Label 'mikrofon:uzivo' 'verzija'))." }
        else { Write-Host "Prethodni image ne odgovara posle 90 s: .\mikrofon.ps1 logovi" }
    }
    "stanje" {
        Write-Host "Image-i:"
        foreach ($t in @("mikrofon:uzivo", "mikrofon:prethodni", "mikrofon:test")) { Show-Image $t }
        docker images mikrofon --format "{{.Repository}}:{{.Tag}}" | Where-Object { $_ -like "mikrofon:test-*" } | ForEach-Object { Show-Image $_ }
        Write-Host "Kontejneri:"
        docker ps -a --filter "name=mikrofon" --format "  {{.Names}}  {{.Image}}  {{.Status}}"
        try { $s = Invoke-RestMethod -Uri http://127.0.0.1:8000/stanje.json -TimeoutSec 4; Write-Host "Uzivo: $($s.stanje), verzija $($s.verzija)" }
        catch { Write-Host "Uzivo ne odgovara na 127.0.0.1:8000." }
    }
    "logovi" {
        if ($Test) { docker compose -f docker-compose.test.yml logs -f --tail 100 uzivo }
        else { docker compose logs -f --tail 100 uzivo }
    }
    "ocisti" {
        $used = docker ps -a --format "{{.Image}}"
        docker images mikrofon --format "{{.Repository}}:{{.Tag}}" | Where-Object { $_ -like "mikrofon:test-*" -and $used -notcontains $_ } |
            ForEach-Object { docker rmi $_ | Out-Null; Write-Host "Uklonjen $_" }
        docker images mikrofon --filter dangling=true -q | ForEach-Object { docker rmi $_ 2>$null | Out-Null }
        docker images --filter dangling=true --filter "label=zailiprotiv.grana" -q | ForEach-Object { docker rmi $_ 2>$null | Out-Null }
        Write-Host "Ostaju:"; docker images mikrofon --format "  {{.Repository}}:{{.Tag}}  {{.Size}}"
    }
}
