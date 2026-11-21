# Scrittura raw di usbdisk.img su \\.\PhysicalDrive2 (Kingston DataTraveler).
# ESEGUIRE COME AMMINISTRATORE.
$ErrorActionPreference = 'Stop'
Start-Transcript -Path 'C:\Users\emili\Desktop\gbos-x1p\tools\qemu_bench\write_usb-log.txt'

try {
    $srcLocal = 'C:\Users\emili\Desktop\gbos-x1p\tools\qemu_bench\usbdisk.img'
    if (-not (Test-Path $srcLocal)) {
        $src = '\\wsl.localhost\Ubuntu-24.04\home\zero89\gbos-usb\usbdisk.img'
        Write-Host "Copio $src -> $srcLocal"
        Copy-Item $src $srcLocal -Force
    }
    Write-Host ("dimensione locale: {0:N0}" -f (Get-Item $srcLocal).Length)

    $disk = Get-Disk -Number 2
    Write-Host "Disco 2: $($disk.FriendlyName) / $($disk.PartitionStyle) / $($disk.Size)"
    if ($disk.FriendlyName -notlike '*Kingston*') { throw "disco 2 non e' la Kingston" }

    $in = [IO.File]::OpenRead($srcLocal)
    $out = [IO.File]::Open('\\.\PhysicalDrive2', [IO.FileMode]::Open,
                           [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    $out.Seek(0, 'Begin') | Out-Null
    $buf = New-Object byte[] (4 * 1024 * 1024)
    $total = 0
    while (($n = $in.Read($buf, 0, $buf.Length)) -gt 0) {
        $out.Write($buf, 0, $n)
        $total += $n
    }
    $out.Flush()
    Write-Host "copiati $total byte"

    $tail = New-Object byte[] (1MB)
    $out.Seek($disk.Size - 1MB, 'Begin') | Out-Null
    $out.Write($tail, 0, $tail.Length)
    $out.Flush(); $out.Close(); $in.Close()
    Write-Host 'FATTO: MBR+partizioni scritti, GPT backup azzerata.'
} catch {
    Write-Host "ERRORE: $_" -ForegroundColor Red
}
Stop-Transcript
