param(
    [Parameter(Mandatory = $true)]
    [string]$Uri
)

$LogPath = Join-Path $env:TEMP "infrascope-nsm.log"

function Write-Log([string]$text) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $text"
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
}

function Show-Error($text) {
    Add-Type -AssemblyName PresentationFramework | Out-Null
    [System.Windows.MessageBox]::Show($text, "InfraScope NetSupport Helper") | Out-Null
    Write-Log "ERROR: $text"
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

    return [uri]::UnescapeDataString($payload).Trim().Trim("/")
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

    try {
        $appPath = (Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Pcictlui.exe" -ErrorAction Stop)."(Default)"
        if ($appPath -and (Test-Path $appPath)) {
            return $appPath
        }
    } catch {
        # ignore
    }

    try {
        $appPathWow = (Get-ItemProperty -Path "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\Pcictlui.exe" -ErrorAction Stop)."(Default)"
        if ($appPathWow -and (Test-Path $appPathWow)) {
            return $appPathWow
        }
    } catch {
        # ignore
    }

    return $null
}

$target = Resolve-TargetFromUri -rawUri $Uri
Write-Log "Incoming URI: $Uri"
if (-not $target) {
    Show-Error "Не удалось определить hostname из ссылки: $Uri"
    exit 1
}
Write-Log "Resolved target: $target"

$exe = Find-NetSupportExecutable
if (-not $exe) {
    Show-Error "Pcictlui.exe не найден. Установите NetSupport Manager на этот ПК."
    exit 1
}
Write-Log "Using executable: $exe"

try {
    # Force TCP/IP and provide hostname in both name/address forms.
    # /C <name> populates client name, /C >address populates address entry.
    $args = @("/U", "TC", "/C", $target, "/C", ">$target", "/VC")
    Start-Process -FilePath $exe -ArgumentList $args
    Write-Log "Connect command sent: $($args -join ' ')"
} catch {
    Show-Error "Не удалось запустить NetSupport Manager: $($_.Exception.Message)"
    exit 1
}
