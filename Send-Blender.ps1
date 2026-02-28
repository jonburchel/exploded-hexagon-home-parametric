<#
.SYNOPSIS
    Send a Python command to Blender's remote console.
.EXAMPLE
    .\Send-Blender.ps1 "bpy.context.scene.render.engine"
    .\Send-Blender.ps1 "bpy.context.scene.camera.location"
    .\Send-Blender.ps1 -File "src\fix_render.py"
#>
param(
    [Parameter(Position=0)]
    [string]$Command,
    [string]$File,
    [int]$Port = 9876
)

if ($File) {
    $code = Get-Content -Raw $File
    $Command = $code
}

if (-not $Command) {
    Write-Host "Usage: .\Send-Blender.ps1 'python code'"
    Write-Host "       .\Send-Blender.ps1 -File script.py"
    exit 1
}

try {
    $tcp = New-Object System.Net.Sockets.TcpClient("127.0.0.1", $Port)
    $stream = $tcp.GetStream()
    $writer = New-Object System.IO.StreamWriter($stream)
    $reader = New-Object System.IO.StreamReader($stream)
    $writer.WriteLine($Command)
    $writer.Flush()
    $tcp.Client.Shutdown([System.Net.Sockets.SocketShutdown]::Send)
    $response = $reader.ReadToEnd().TrimEnd()
    Write-Host $response
    $tcp.Close()
} catch {
    Write-Host "Could not connect to Blender on port $Port."
    Write-Host "Start the server first: exec(open(r'F:\home\exploded-hexagon-home\src\blender_remote.py').read())"
    Write-Host "Error: $_"
}
