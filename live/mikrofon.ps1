# The live service's two images: a change is tried as the test, and only the image the test ran goes live.
#   .\mikrofon.ps1 test [-Novo]   build the working tree as mikrofon:test and run it at http://127.0.0.1:8001/
#                                 (-Novo: everything fetched afresh, the newest yt-dlp among it)
#   .\mikrofon.ps1 uzivo          the tested image goes live (mikrofon:uzivo); the one it replaces is kept
#   .\mikrofon.ps1 nazad          the image that was live before goes live again
#   .\mikrofon.ps1 stanje         what runs, and which image is which
param(
    [Parameter(Position = 0)][ValidateSet("test", "uzivo", "nazad", "stanje")][string]$Korak = "stanje",
    [switch]$Novo
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
