# The live service's images: a change is tried as a test, and only an image of a clean origin/main goes live.
#   .\mikrofon.ps1 test [-Novo] [-Jedan]   build this working tree and run it beside the live service, as two containers,
#                                 the measuring and the page (-Jedan: as one; -Novo: everything fetched afresh, the newest
#                                 yt-dlp among it). From the main clone on main: mikrofon:test at http://127.0.0.1:8001/;
#                                 from a worktree: mikrofon:test-<branch> on a port of its own.
#   .\mikrofon.ps1 uzivo [-Deo strana|merenje|oba]   mikrofon:test goes live, if it was built from a clean origin/main
#                                 (-Ipak: whatever it is). strana (as with none named): the page alone, at once, while the
#                                 measuring goes on. merenje, oba: while someone speaks it waits for the turn to end
#                                 (-Cekaj minutes at most, 10 by default; -Odmah: at once). What doesn't answer within
#                                 90 s is put back as it was. The page goes on during the restart.
#   .\mikrofon.ps1 uzivo -Jedan   the same while the live service is one container, which it stays; -Deo oba makes it two
#   .\mikrofon.ps1 nazad -Deo strana|merenje|oba   the part's image that was live before goes live again (at once)
#   .\mikrofon.ps1 nazad -Jedan   two containers back to one, of the measuring's image (then, if it is the image that is
#                                 at fault, `nazad`: the one before)
#   .\mikrofon.ps1 stanje         what runs, which image is which commit, and which commits of each part are not live
#   .\mikrofon.ps1 logovi [-Deo strana|merenje] [-Test]   the live service's log (or this tree's test's), followed
#   .\mikrofon.ps1 ocisti         remove what nothing uses: untagged images, and the tests (containers, images,
#                                 volumes) of worktrees that are gone
#                                 and the build cache older than a day
param(
    [Parameter(Position = 0)][ValidateSet("test", "uzivo", "nazad", "stanje", "logovi", "ocisti")][string]$Korak = "stanje",
    [switch]$Novo,
    [switch]$Odmah,
    [switch]$Ipak,
    [switch]$Test,
    [switch]$Jedan,
    [ValidateSet("strana", "merenje", "oba")][string]$Deo,
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

# The test's compose files: the second makes it two containers. Both name every container a test may have, so that
# stopping it and its log take both.
$TestOne = @("-f", "docker-compose.test.yml")
$TestTwo = $TestOne + @("-f", "docker-compose.test.dva.yml")
# The live service's: two containers (docker-compose.yml, which compose itself takes), or the one before.
$LiveOne = @("-f", "docker-compose.jedan.yml")
$Parts = @{
    merenje = @{ Service = "merenje"; Image = "mikrofon:uzivo"; Before = "mikrofon:prethodni" }
    strana  = @{ Service = "uzivo"; Image = "mikrofon:strana"; Before = "mikrofon:strana-prethodni" }
}
# The modules of live/uzivo only one of the two loads (a test compares them with what they import): for `stanje`. The
# rest of what an image is made of is both's.
$OnlyPage = @("deljenje", "main", "mejl", "page", "picture", "prati", "pretplata", "texts")
$OnlyMeasuring = @("dnevnik", "glas", "grafika", "komadi", "merenje", "ocr", "sada", "worker")
$PageFiles = @("live/uzivo/static", "src/zailiprotiv/static/fonts", "src/zailiprotiv/og", "src/zailiprotiv/templates/mikrofon.js", "src/zailiprotiv/templates/mikrofon.css")
$ImageFiles = @("live/uzivo", "live/Dockerfile", "live/requirements.txt", "live/constraints.txt", "live/ulaz.sh", "live/deno.sh", "live/docker-compose.yml", "src/zailiprotiv/cyrillic.py", "data/settings.json")

# Whether the live service is two containers: the measuring has one of its own, running or not.
function Test-Two {
    return [bool](docker ps -aq --filter "label=com.docker.compose.project=mikrofon" --filter "label=com.docker.compose.service=merenje")
}

# Whether the page answers with the moment, so whether the measuring is alive (two containers: 503 when it is not).
function Test-Moment {
    try { Invoke-RestMethod -Uri http://127.0.0.1:8000/stanje.json -TimeoutSec 5 | Out-Null; return $true } catch { return $false }
}

# Until the page answers on its port (and, given a commit, says it runs that one): $true, or $false after $Seconds.
function Wait-Page([int]$Port, [string]$Version, [int]$Seconds = 90, [string]$Path = "stanje.json") {
    $until = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $until) {
        try {
            $s = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/$Path" -TimeoutSec 4
            if (-not $Version -or $s.verzija -eq $Version) { return $true }
        } catch {}
        Start-Sleep -Seconds 2
    }
    return $false
}

# Until Docker's check of the measuring passes (it asks for this image's own commit: merenje.healthy).
function Wait-Measuring([int]$Seconds = 90) {
    $until = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $until) {
        $id = docker compose ps -aq merenje
        if ($id -and "$(docker inspect -f '{{.State.Health.Status}}' $id)" -eq "healthy") { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

# The restart in a gap (20 Nov 2026): the edge keeps the page's last answer and the service takes up the turn on,
# so a restart mid-speech shows nothing wrong; still, between turns it misses not even a few frames of anyone's.
function Wait-Gap([int]$Minutes) {
    $until = (Get-Date).AddMinutes($Minutes)
    $said = $false
    $quiet = $null
    while ((Get-Date) -lt $until) {
        try { $s = Invoke-RestMethod -Uri http://127.0.0.1:8000/stanje.json -TimeoutSec 5 } catch { return }
        # nor while the chair speaks: the words of the moment ("titl") are still fresh (24 Nov 2026: a restart in the
        # second the chair gave a break lost the break, so nobody would have been told when it ended)
        # (24 Nov 2026, later: in a debate the chair always speaks, so waiting for silence ran out the time and the restart
        # fell mid-speech; twenty seconds after a turn's end is enough, as the sound not written down survives it)
        if ($s.stanje -ne "govori") {
            if (-not $quiet) { $quiet = Get-Date }
            if (-not @($s.titl).Count -or ((Get-Date) - $quiet).TotalSeconds -ge 20) { return }
        } else { $quiet = $null }
        if (-not $said) { Write-Host "Govori $($s.sada.ime) (ili predsedavajuci): cekam kraj govora (najvise $Minutes min; -Odmah za odmah)..."; $said = $true }
        Start-Sleep -Seconds 3
    }
    Write-Host "Govor traje duze od $Minutes min: menjam sada (stranica i govor se nastavljaju)."
}

# The one container: put live, wait until it answers, and if it doesn't, put the image before back.
function Set-LiveOne([string]$Version) {
    docker compose @LiveOne up -d; Assert-Ok "Pokretanje uzivo"
    if (Wait-Page 8000 $Version 90) { return }
    if (-not (Get-ImageId "mikrofon:prethodni")) { throw "Novi image ne odgovara posle 90 s, a prethodnog nema: pogledaj .\mikrofon.ps1 logovi." }
    Restore-Image "merenje"
    docker compose @LiveOne up -d; Assert-Ok "Pokretanje prethodnog"
    throw "Novi image ($Version) ne odgovara posle 90 s: vracen je prethodni. Pogledaj logove testa."
}

# One part's container, of its image, the other left alone (--no-deps), and whether it answers. While the measuring is
# down the page is asked only whether it is there: that it then says nothing of the moment is right.
function Start-Part([string]$Part, [string]$Version, [bool]$Moment = $true) {
    docker compose up -d --no-deps $Parts[$Part].Service | Out-Host
    if ($LASTEXITCODE -ne 0) { return $false }
    if ($Part -eq "merenje") { return (Wait-Measuring) }
    return (Wait-Page 8000 $Version 90 $(if ($Moment) { "stanje.json" } else { "zdravlje" }))
}

# The tested image as a part's, the one before it kept; $false when it is live already (then nothing is kept over).
function Set-Image([string]$Part) {
    $p = $Parts[$Part]
    $now = Get-ImageId $p.Image
    if ($now -and $now -eq (Get-ImageId "mikrofon:test")) { return $false }
    if ($now) { docker tag $p.Image $p.Before; Assert-Ok "Cuvanje prethodnog" }
    docker tag mikrofon:test $p.Image; Assert-Ok "Oznacavanje"
    return $true
}

function Restore-Image([string]$Part) {
    $p = $Parts[$Part]
    if (-not (Get-ImageId $p.Before)) { throw "Nema $($p.Before)." }
    docker tag $p.Before $p.Image; Assert-Ok "Vracanje prethodnog"
}

# The page and the measuring run together only when they are of one format (state_base.FORMAT).
function Assert-Format([string]$A, [string]$B) {
    $x, $y = (Get-Label $A "format"), (Get-Label $B "format")
    if (-not $Ipak -and (-not $x -or $x -ne $y)) { throw "Format: $A '$x', $B '$y'. Idu zajedno (-Deo oba), ili -Ipak." }
}

# From two containers back to one: the measuring is taken away before the one that writes in its place comes.
function Exit-Two([string]$Version) {
    docker compose rm -f -s merenje; Assert-Ok "Uklanjanje merenja"
    docker compose @LiveOne up -d; Assert-Ok "Pokretanje uzivo"
    if (-not (Wait-Page 8000 $Version 90)) { throw "Jedan kontejner ne odgovara posle 90 s: .\mikrofon.ps1 logovi" }
}

# From one container to two. The old one is stopped first: the new measuring would wait for its lock, and the page for
# the measuring. The edge gives the page's last answers meanwhile. $Changed: the one container's image was another.
function Enter-Two([string]$Version, [bool]$Changed) {
    docker compose stop -t 120 uzivo; Assert-Ok "Zaustavljanje"
    if ((Start-Part "merenje" $Version) -and (Start-Part "strana" $Version)) { docker compose up -d --no-deps tunel; return }
    Write-Host "Kao dva ne radi: vracam jedan kontejner."
    docker compose logs --tail 40 merenje uzivo
    if ($Changed) { Restore-Image "merenje" }
    Exit-Two ""
    throw "Prelazak na dva nije uspeo: uzivo je jedan kontejner, $(Get-Label 'mikrofon:uzivo' 'verzija')."
}

# The commits of origin/main that touch a part and are not in its image, for `stanje`.
function Show-Waiting([string]$Part, [string]$From) {
    $others = if ($Part -eq "strana") { $OnlyMeasuring } else { $OnlyPage }
    $paths = $ImageFiles + @($others | ForEach-Object { ":(exclude)live/uzivo/$_.py" })
    if ($Part -eq "strana") { $paths += $PageFiles } else { $paths += ":(exclude)live/uzivo/static" }
    Push-Location $here
    $lines = @(git log --oneline "$From..origin/main" "--" $paths)
    $known = ($LASTEXITCODE -eq 0)
    Pop-Location
    if (-not $From -or -not $known) { Write-Host "  $Part ($From): ne znam taj commit (git fetch?)"; return }
    Write-Host "  $Part ($From): $(if ($lines.Count) { "$($lines.Count) ceka" } else { 'sve je uzivo' })"
    $lines | ForEach-Object { Write-Host "    $_" }
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
        if ($Novo) { docker compose @TestOne build --pull --no-cache; Assert-Ok "Build" }
        # Two services never write in one volume (the lock, uzivo/sada.py): the form that ran before is stopped first, or
        # the new measuring would wait for it.
        if (-not $Jedan) {
            docker compose @TestTwo build; Assert-Ok "Build"
            docker compose @TestTwo stop; Assert-Ok "Zaustavljanje testa"
            docker compose @TestTwo up -d; Assert-Ok "Pokretanje testa"
        } else {
            docker compose @TestOne build; Assert-Ok "Build"
            docker compose @TestTwo rm -f -s merenje; Assert-Ok "Uklanjanje merenja"
            docker compose @TestOne up -d; Assert-Ok "Pokretanje testa"
        }
        $ok = Wait-Page $Tree.Port $Tree.Sha 90
        $dirty = if ($Tree.Clean -eq "ne") { ", sa izmenama koje nisu commit-ovane" } else { "" }
        Write-Host $(if ($Jedan) { "Kao jedan kontejner." } else { "Kao dva kontejnera: merenje i strana." })
        Write-Host "Test $($Tree.Image): $($Tree.Sha) sa grane $($Tree.Branch)$dirty"
        if ($ok) { Write-Host "Radi na http://127.0.0.1:$($Tree.Port)/  (logovi: .\mikrofon.ps1 logovi -Test)" }
        else { Write-Host "Ne odgovara posle 90 s: .\mikrofon.ps1 logovi -Test" }
    }
    "uzivo" {
        if (-not $Tree.IsMain) { throw "Uzivo se pusta iz glavnog klona ($($Tree.Main)), na grani main." }
        $testId = Get-ImageId "mikrofon:test"
        if (-not $testId) { throw "Nema mikrofon:test: prvo .\mikrofon.ps1 test." }
        if (-not (Test-Path .tunnel.env)) { throw "Nema .tunnel.env (TUNNEL_TOKEN=... iz Cloudflare-a)." }
        git fetch -q origin
        $want = (git rev-parse --short origin/main).Trim()
        $v, $b, $c = (Get-Label "mikrofon:test" "verzija"), (Get-Label "mikrofon:test" "grana"), (Get-Label "mikrofon:test" "cisto")
        if (-not $Ipak -and ($v -ne $want -or $b -ne "main" -or $c -ne "da")) {
            $what = if ($v) { "$v sa grane $b$(if ($c -eq 'ne') { ', sa izmenama koje nisu commit-ovane' })" } else { "bez oznake verzije" }
            throw "mikrofon:test je $what, a origin/main je $want. Prvo: git pull; .\mikrofon.ps1 test (ili -Ipak)."
        }
        $two = Test-Two
        if ($Jedan) {
            if ($Deo) { throw "-Jedan i -Deo ne idu zajedno." }
            if ($two) { throw "Uzivo su dva kontejnera: pusti deo (-Deo), ili prvo .\mikrofon.ps1 nazad -Jedan." }
            if ($testId -eq (Get-ImageId "mikrofon:uzivo")) { Write-Host "Testirani image je vec uzivo." }
            else {
                if (-not $Odmah) { Wait-Gap $Cekaj }
                Set-Image "merenje" | Out-Null
            }
            Set-LiveOne $v
            $what = "jedan kontejner"
        } elseif (-not $two) {
            if ($Deo -ne "oba") { throw "Uzivo je jedan kontejner: -Jedan (tako ostaje) ili -Deo oba (prelazak na dva)." }
            if (-not (Get-Label "mikrofon:test" "format")) { throw "mikrofon:test je stariji od dva kontejnera." }
            if (-not $Odmah) { Wait-Gap $Cekaj }
            $changed = Set-Image "merenje"
            Set-Image "strana" | Out-Null
            Enter-Two $v $changed
            $what = "sada dva kontejnera"
        } else {
            $what = if ($Deo) { $Deo } else { "strana" }
            if ($what -eq "strana") { Assert-Format "mikrofon:test" "mikrofon:uzivo" }
            if ($what -eq "merenje") { Assert-Format "mikrofon:test" "mikrofon:strana" }
            if ($what -ne "strana" -and -not $Odmah) { Wait-Gap $Cekaj }
            $moment = ($what -eq "oba") -or (Test-Moment)
            $went = @()
            foreach ($one in $(if ($what -eq "oba") { @("merenje", "strana") } else { @($what) })) {  # the measuring first
                if (Set-Image $one) { $went += $one } else { Write-Host "$($one): testirani image je vec uzivo." }
                if (Start-Part $one $v $moment) { continue }
                # What went live in this run goes back: of two formats the parts are right only together.
                Write-Host "$one ($v) ne odgovara posle 90 s."
                docker compose logs --tail 40 $Parts[$one].Service
                foreach ($back in $went) {
                    Restore-Image $back
                    if (-not (Start-Part $back "" $false)) { Write-Host "Ni prethodni ne odgovara posle 90 s ($back)." }
                }
                throw "Novi image ($v) nije uzivo. Vraceno: $(if ($went) { $went -join ', ' } else { 'nista, isti image je bio uzivo' })."
            }
        }
        # The test reads the same broadcast with Whisper too; once its image is live it only takes the cores.
        docker compose @TestTwo stop
        Write-Host "Uzivo radi $v, $what (https://mikrofon.zailiprotiv.rs/stanje.json kaze `"verzija`" i `"merenje`"); test zaustavljen."
    }
    "nazad" {
        $two = Test-Two
        if ($Jedan) {
            if (-not $two) { throw "Uzivo je vec jedan kontejner." }
            Exit-Two ""
            Write-Host "Uzivo je jedan kontejner ($(Get-Label 'mikrofon:uzivo' 'verzija'))."
        } elseif (-not $two) {
            if ($Deo) { throw "Uzivo je jedan kontejner: .\mikrofon.ps1 nazad" }
            Restore-Image "merenje"
            docker compose @LiveOne up -d; Assert-Ok "Pokretanje uzivo"
            if (Wait-Page 8000 "" 90) { Write-Host "Uzivo ponovo radi prethodni image ($(Get-Label 'mikrofon:uzivo' 'verzija'))." }
            else { Write-Host "Prethodni image ne odgovara posle 90 s: .\mikrofon.ps1 logovi" }
        } else {
            if (-not $Deo) { throw "Uzivo su dva kontejnera: -Deo strana, merenje ili oba (ili -Jedan)." }
            if ($Deo -eq "strana") { Assert-Format "mikrofon:strana-prethodni" "mikrofon:uzivo" }
            if ($Deo -eq "merenje") { Assert-Format "mikrofon:prethodni" "mikrofon:strana" }
            foreach ($one in $(if ($Deo -eq "oba") { @("merenje", "strana") } else { @($Deo) })) {
                Restore-Image $one
                $v = Get-Label $Parts[$one].Image "verzija"
                if (Start-Part $one $v $false) { Write-Host "$($one): uzivo ponovo radi prethodni image ($v)." }
                else { Write-Host "$($one): prethodni image ($v) ne odgovara posle 90 s: .\mikrofon.ps1 logovi -Deo $one" }
            }
        }
    }
    "stanje" {
        Write-Host "Image-i:"
        foreach ($t in @("mikrofon:uzivo", "mikrofon:prethodni", "mikrofon:strana", "mikrofon:strana-prethodni", "mikrofon:test")) { Show-Image $t }
        docker images mikrofon --format "{{.Repository}}:{{.Tag}}" | Where-Object { $_ -like "mikrofon:test-*" } | ForEach-Object { Show-Image $_ }
        Write-Host "Kontejneri:"
        docker ps -a --filter "name=mikrofon" --format "  {{.Names}}  {{.Image}}  {{.Status}}"
        try { $s = Invoke-RestMethod -Uri http://127.0.0.1:8000/stanje.json -TimeoutSec 4; Write-Host "Uzivo: $($s.stanje), verzija $($s.verzija), merenje $($s.merenje)" }
        catch { Write-Host "Uzivo ne odgovara na 127.0.0.1:8000 (ili merenje ne radi)." }
        $two = Test-Two
        Write-Host "Nije uzivo, od onoga sto je na origin/main (uzivo $(if ($two) { 'su dva kontejnera' } else { 'je jedan kontejner' })):"
        foreach ($one in @("strana", "merenje")) { Show-Waiting $one (Get-Label $(if ($two) { $Parts[$one].Image } else { "mikrofon:uzivo" }) "verzija") }
    }
    "logovi" {
        $which = if ($Deo -and $Deo -ne "oba") { @($Parts[$Deo].Service) } else { @("merenje", "uzivo") }
        if ($Test) { docker compose @TestTwo logs -f --tail 100 $which }
        else { docker compose logs -f --tail 100 $which }
    }
    "ocisti" {
        # The tests of worktrees that are gone: their containers, images and volumes (the script pocisti.sh runs too).
        sh (Join-Path $here "tools/pocisti-projekat.sh")
        docker images mikrofon --filter dangling=true -q | ForEach-Object { docker rmi $_ 2>$null | Out-Null }
        docker images --filter dangling=true --filter "label=zailiprotiv.grana" -q | ForEach-Object { docker rmi $_ 2>$null | Out-Null }
        docker builder prune -f --filter "until=24h" | Select-Object -Last 1
        Write-Host "Ostaju:"; docker images mikrofon --format "  {{.Repository}}:{{.Tag}}  {{.Size}}"
    }
}
