param([Parameter(Mandatory=$true)][string]$Root)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath $Root).Path
$python = Join-Path $Root '.venv\Scripts\pythonw.exe'
$launcher = Join-Path $Root 'scripts\launch_live.py'
if (!(Test-Path -LiteralPath $python) -or !(Test-Path -LiteralPath $launcher)) {
    throw 'Missing verified game launcher or project Python.'
}
$sha = [Security.Cryptography.SHA256]::Create()
$suffix = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Root.ToLowerInvariant()))).Replace('-', '').Substring(0,12)
$name = 'RobotomyAI-Game-' + $suffix
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$service = New-Object -ComObject 'Schedule.Service'
$service.Connect()
$folder = $service.GetFolder('\')
$arguments = '-X utf8 "' + $launcher + '" --scheduled-worker'
$existing = $null
try { $existing = $folder.GetTask($name) } catch {
    if ($_.Exception.HResult -ne -2147024894) { throw }
}
if ($null -ne $existing) {
    $def = $existing.Definition
    $owner = $def.Principal.UserId
    if ($owner -notmatch '^S-1-') {
        $owner = ([Security.Principal.NTAccount]::new($owner)).Translate([Security.Principal.SecurityIdentifier]).Value
    }
    if ($def.Actions.Count -ne 1 -or $def.Actions.Item(1).Path -ne $python -or
        $def.Actions.Item(1).Arguments -ne $arguments -or $owner -ne $sid) {
        throw 'Existing task identity differs; refusing to replace or execute it.'
    }
    if ($existing.State -eq 4 -or $existing.State -eq 2) {
        @{task=$name; state='already_running'} | ConvertTo-Json -Compress
        exit 0
    }
}
$task = $service.NewTask(0)
$task.RegistrationInfo.Description = 'Robotomy private game. On demand only; independent of Codex. No automatic restart.'
$task.Principal.UserId = $sid
$task.Principal.LogonType = 3 # Existing interactive user session; no stored password.
$task.Principal.RunLevel = 0 # Least privilege, no elevation.
$task.Settings.ExecutionTimeLimit = 'PT0S'
$task.Settings.DisallowStartIfOnBatteries = $false
$task.Settings.StopIfGoingOnBatteries = $false
$task.Settings.AllowHardTerminate = $false
$task.Settings.MultipleInstances = 2 # Ignore duplicate requests.
$task.Settings.AllowDemandStart = $true
$action = $task.Actions.Create(0)
$action.Path = $python
$action.Arguments = $arguments
$action.WorkingDirectory = $Root
$registered = $folder.RegisterTaskDefinition($name, $task, 6, $sid, $null, 3)
$null = $registered.Run($null)
@{task=$name; state='requested'} | ConvertTo-Json -Compress
