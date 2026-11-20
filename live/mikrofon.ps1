# The live service's two images: a change is tried as the test, and only the image the test ran goes live.
#   .\mikrofon.ps1 test [-Novo]   build the working tree as mikrofon:test and run it at http://127.0.0.1:8001/
#                                 (-Novo: everything fetched afresh, the newest yt-dlp among it)
#   .\mikrofon.ps1 uzivo          the tested image goes live (mikrofon:uzivo); the one it replaces is kept. While
#                                 someone speaks it waits for the turn to end (-Cekaj minutes at most, 10 by
#                                 default; -Odmah: at once). The page goes on in the few seconds of the restart.
#   .\mikrofon.ps1 nazad          the image that was live before goes live again (at once)
#   .\mikrofon.ps1 stanje         what runs, and which image is which
param(
    [Parameter(Position = 0)][ValidateSet("test", "uzivo", "nazad", "stanje")][string]$Korak = "stanje",
    [switch]$Novo,
    [switch]$Odmah,
    [int]$Cekaj = 10
)
# Not "Stop": Windows PowerShell takes docker's progress on stderr for an error. Exit codes are checked (Assert-Ok).
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

function Get-ImageId([string]$Tag) {
    $id = docker images -q $Tag
    if ($id) { return $id.Trim() }
    return ""
}

function Assert-Ok([string]$What) {
    if ($LASTEXITCODE -ne 0) { throw "$What nije uspelo (izlaz $LASTEXITCODE)." }
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

switch ($Korak) {
    "test" {
        if ($Novo) {
            docker compose -f docker-compose.test.yml build --pull --no-cache; Assert-Ok "Build"
        }
        docker compose -f docker-compose.test.yml up -d --build; Assert-Ok "Pokretanje testa"
        Write-Host "Test radi na http://127.0.0.1:8001/  (logovi: docker compose -f docker-compose.test.yml logs -f)"
    }
    "uzivo" {
        $test = Get-ImageId "mikrofon:test"
        if (-not $test) { throw "Nema mikrofon:test: prvo .\mikrofon.ps1 test." }
        if (-not (Test-Path .tunnel.env)) { throw "Nema .tunnel.env (TUNNEL_TOKEN=... iz Cloudflare-a)." }
        $live = Get-ImageId "mikrofon:uzivo"
        if ($live -ne $test -and -not $Odmah) { Wait-Gap $Cekaj }
        if ($live -eq $test) {
            Write-Host "Testirani image je vec uzivo."
        } else {
            if ($live) { docker tag mikrofon:uzivo mikrofon:prethodni; Assert-Ok "Cuvanje prethodnog" }
            docker tag mikrofon:test mikrofon:uzivo; Assert-Ok "Oznacavanje"
        }
        docker compose up -d; Assert-Ok "Pokretanje uzivo"
        # The test reads the same broadcast with Whisper too; once its image is live it only takes the cores.
        docker compose -f docker-compose.test.yml stop
        Write-Host "Uzivo radi image $test (test zaustavljen; podaci mu ostaju)."
    }
    "nazad" {
        if (-not (Get-ImageId "mikrofon:prethodni")) { throw "Nema mikrofon:prethodni." }
        docker tag mikrofon:prethodni mikrofon:uzivo; Assert-Ok "Oznacavanje"
        docker compose up -d; Assert-Ok "Pokretanje uzivo"
        Write-Host "Uzivo ponovo radi prethodni image."
    }
    "stanje" {
        docker images mikrofon
        docker compose ps
        docker compose -f docker-compose.test.yml ps
    }
}
