param()

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPath = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$requirementsPath = Join-Path $projectRoot "requirements.txt"

function New-ProjectVenv {
    param(
        [string]$TargetPath
    )

    $venvArgs = @("-m", "venv")
    if (Test-Path $TargetPath) {
        $venvArgs += "--clear"
    }
    $venvArgs += $TargetPath

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        try {
            & $py.Source -3.11 @venvArgs
            if ($LASTEXITCODE -eq 0) {
                return
            }
        }
        catch {
        }

        & $py.Source -3 @venvArgs
        if ($LASTEXITCODE -eq 0) {
            return
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        & $python.Source @venvArgs
        if ($LASTEXITCODE -eq 0) {
            return
        }
    }

    throw "Nao foi possivel criar a .venv. Instale o Python 3.11+ ou configure o launcher 'py'."
}

$venvHealthy = $false
if (Test-Path $venvPython) {
    try {
        & $venvPython -c "import sys" | Out-Null
        $venvHealthy = $LASTEXITCODE -eq 0
    }
    catch {
        $venvHealthy = $false
    }
}

if (-not $venvHealthy) {
    Write-Host "Bootstrapping .venv em $venvPath"
    New-ProjectVenv -TargetPath $venvPath
}

if (-not (Test-Path $venvPython)) {
    throw "A .venv foi criada, mas o interpretador nao foi encontrado em $venvPython"
}

Write-Host "Atualizando pip na .venv"
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao atualizar o pip na .venv."
}

Write-Host "Instalando dependencias de $requirementsPath"
& $venvPython -m pip install -r $requirementsPath
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao instalar as dependencias do projeto."
}