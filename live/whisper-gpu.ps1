# Whisper on the graphics card (22 Nov 2026, the maintainer's choice): whisper.cpp's server with large-v3-turbo on
# the computer's Radeon, through Vulkan, beside Docker. The live service (and its tests) send it the sound
# (WHISPER_URL, http://host.docker.internal:8178); while it does not answer they write on the CPU as before.
# Measured on 5 min of the 19 Nov sitting: 22x faster than speech (the CPU 4.5x), a piece of 5 s in 0.4 s.
#
#   .\whisper-gpu.ps1 napravi   build whisper.cpp at the commit below with Vulkan, fetch the two models, checked
#   .\whisper-gpu.ps1 pokreni   start the server, hidden, if it is not running (127.0.0.1:8178 only)
#   .\whisper-gpu.ps1 stanje    whether it runs and answers, and on which card
#   .\whisper-gpu.ps1 zaustavi  stop it
#   .\whisper-gpu.ps1 zakazi    start it with Windows (a line in the user's Startup folder; no admin)
#
# Needs: Visual Studio Build Tools with C++ (its CMake), the Vulkan SDK (winget KhronosGroup.VulkanSDK), git.
param([Parameter(Position = 0)][ValidateSet("napravi", "pokreni", "stanje", "zaustavi", "zakazi")][string]$Korak = "stanje")
$ErrorActionPreference = "Stop"

$Home_ = Join-Path $HOME "zailiprotiv-whisper"
$Src = Join-Path $Home_ "whisper.cpp"
$Exe = Join-Path $Src "build\bin\Release\whisper-server.exe"
$Commit = "5eaee0cc9024eb9e9a99469199920c8b7f5cb9ec"   # whisper.cpp, 20 Nov 2026: built and measured
$Models = @{
    "ggml-large-v3-turbo.bin"  = @("https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin", "1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69")
    "ggml-silero-v6.2.0.bin"   = @("https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin", "2aa269b785eeb53a82983a20501ddf7c1d9c48e33ab63a41391ac6c9f7fb6987")
}
$Port = 8178
$Log = Join-Path $Home_ "server.log"

function Get-Server { Get-Process whisper-server -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $Exe } }

function Test-Answer {
    try { $null = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 "http://127.0.0.1:$Port/"; return $true } catch { return $false }
}

switch ($Korak) {
    "napravi" {
        New-Item -ItemType Directory -Force $Home_ | Out-Null
        if (-not (Test-Path $Src)) { git clone -q https://github.com/ggml-org/whisper.cpp $Src }
        git -C $Src fetch -q origin $Commit; git -C $Src checkout -q $Commit
        $sdk = Get-ChildItem C:\VulkanSDK -Directory -ErrorAction SilentlyContinue | Sort-Object Name | Select-Object -Last 1
        if (-not $sdk) { throw "Nema Vulkan SDK-a: winget install --id KhronosGroup.VulkanSDK -e" }
        $vs = & "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -products * -property installationPath | Select-Object -First 1
        $env:VULKAN_SDK = $sdk.FullName
        $env:PATH = "$($sdk.FullName)\Bin;$vs\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin;$env:PATH"
        cmake -S $Src -B (Join-Path $Src "build") -DGGML_VULKAN=ON -DWHISPER_BUILD_TESTS=OFF | Out-Null
        cmake --build (Join-Path $Src "build") --config Release -j 10 --target whisper-server | Out-Null
        if (-not (Test-Path $Exe)) { throw "whisper-server nije napravljen" }
        $dir = Join-Path $Home_ "modeli"; New-Item -ItemType Directory -Force $dir | Out-Null
        foreach ($name in $Models.Keys) {
            $file = Join-Path $dir $name; $url, $sha = $Models[$name]
            if (-not (Test-Path $file) -or (Get-FileHash $file -Algorithm SHA256).Hash -ne $sha) {
                Write-Host "Preuzimam $name..."; Invoke-WebRequest -UseBasicParsing $url -OutFile $file
            }
            if ((Get-FileHash $file -Algorithm SHA256).Hash -ne $sha) { Remove-Item $file; throw "$name nije onaj koji treba (SHA-256)" }
        }
        Write-Host "Napravljeno: $Exe ($Commit)"
    }
    "pokreni" {
        if (Get-Server) { Write-Host "Vec radi."; return }
        if (-not (Test-Path $Exe)) { throw "Prvo: .\whisper-gpu.ps1 napravi" }
        $m = Join-Path $Home_ "modeli"
        # beam 3 as on the CPU; VAD drops the silence, where Whisper would otherwise make up words
        $args_ = "-m `"$m\ggml-large-v3-turbo.bin`" -l sr -bs 3 -t 4 --host 127.0.0.1 --port $Port --vad -vm `"$m\ggml-silero-v6.2.0.bin`""
        Start-Process -FilePath $Exe -ArgumentList $args_ -WindowStyle Hidden -RedirectStandardError $Log -RedirectStandardOutput "$Log.out" -WorkingDirectory $Home_
        foreach ($i in 1..30) { if (Test-Answer) { break }; Start-Sleep 1 }
        if (Test-Answer) { Write-Host "Radi na http://127.0.0.1:$Port/" } else { throw "Ne odgovara; vidi $Log" }
    }
    "stanje" {
        $p = Get-Server
        if (-not $p) { Write-Host "Ne radi (servis pise na procesoru)."; return }
        $card = Select-String -Path $Log -Pattern "ggml_vulkan: 0 = (.*?) \|" -ErrorAction SilentlyContinue | Select-Object -First 1
        Write-Host ("Radi (pid {0}), odgovara: {1}, kartica: {2}" -f $p.Id, (Test-Answer), $(if ($card) { $card.Matches[0].Groups[1].Value } else { "nepoznato" }))
    }
    "zaustavi" { Get-Server | Stop-Process -Force; Write-Host "Zaustavljeno." }
    "zakazi" {
        $startup = [Environment]::GetFolderPath("Startup")
        $line = "@powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSCommandPath`" pokreni"
        Set-Content -Path (Join-Path $startup "zailiprotiv-whisper.cmd") -Value $line -Encoding ascii
        Write-Host "Pokrece se sa Windowsom ($startup\zailiprotiv-whisper.cmd)."
    }
}
