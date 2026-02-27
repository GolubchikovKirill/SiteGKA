param(
    [Parameter(Mandatory = $true)]
    [string]$Uri
)

function Show-Error($text) {
    Add-Type -AssemblyName PresentationFramework | Out-Null
    [System.Windows.MessageBox]::Show($text, "InfraScope NetSupport Helper") | Out-Null
}

function Resolve-TargetFromUri([string]$rawUri) {
    $value = $rawUri.Trim()
    if (-not $value.ToLower().StartsWith("infrascope-nsm://")) {
        return $null
    }

    $payload = $value.Substring("infrascope-nsm://".Length).TrimStart("/")
    if (-not $payload) {
        return $null
    }

    if ($payload.ToLower().StartsWith("connect?")) {
        $query = $payload.Substring("connect?".Length)
        foreach ($pair in $query.Split("&")) {
            $parts = $pair.Split("=", 2)
            if ($parts.Length -eq 2 -and $parts[0].ToLower() -eq "host") {
                return [uri]::UnescapeDataString($parts[1]).Trim()
            }
        }
        return $null
    }

    return [uri]::UnescapeDataString($payload).Trim()
}

function Find-NetSupportExecutable {
    $paths = @(
        "C:\Program Files (x86)\NetSupport\NetSupport Manager\Pcictlui.exe",
        "C:\Program Files\NetSupport\NetSupport Manager\Pcictlui.exe",
        "C:\Program Files (x86)\NetSupport\NetSupport Manager\PCICTLUI.EXE",
        "C:\Program Files\NetSupport\NetSupport Manager\PCICTLUI.EXE"
    )

    foreach ($path in $paths) {
        if (Test-Path $path) {
            return $path
        }
    }
    return $null
}

function Is-NetSupportAlreadyOpen {
    $proc = Get-Process -Name "Pcictlui" -ErrorAction SilentlyContinue | Select-Object -First 1
    return $null -ne $proc
}

$target = Resolve-TargetFromUri -rawUri $Uri
if (-not $target) {
    Show-Error "Не удалось определить hostname из ссылки: $Uri"
    exit 1
}

$exe = Find-NetSupportExecutable
if (-not $exe) {
    Show-Error "Pcictlui.exe не найден. Установите NetSupport Manager на этот ПК."
    exit 1
}

if (Is-NetSupportAlreadyOpen) {
    # Do not spawn duplicate Manager window.
    exit 0
}

Start-Process -FilePath $exe -ArgumentList @("/C", $target, "/VC")
