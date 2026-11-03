
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# --------------------------------------------------
# StockFlow automated PostgreSQL backup
# --------------------------------------------------

$PgBin = "C:\Program Files\PostgreSQL\18\bin"

$PgDump = Join-Path $PgBin "pg_dump.exe"
$PgRestore = Join-Path $PgBin "pg_restore.exe"

$DbHost = "127.0.0.1"
$DbPort = "5432"
$DbName = "stockflow"
$DbUser = "stockflow_backup"

$BackupDir = "C:\Users\Admin\StockFlowBackups"
$LogDir = Join-Path $BackupDir "logs"

$CredentialPath = Join-Path `
    $env:APPDATA `
    "StockFlow\backup-credential.xml"

$RetentionDays = 30

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

$FinalBackup = Join-Path `
    $BackupDir `
    "stockflow_daily_$Timestamp.dump"

$PartialBackup = "$FinalBackup.partial"
$ChecksumFile = "$FinalBackup.sha256"

$LogFile = Join-Path $LogDir "backup.log"

$PassFile = $null
$PreviousPgpassFile = $env:PGPASSFILE
$ExitCode = 0

# --------------------------------------------------
# Logging
# --------------------------------------------------

New-Item -ItemType Directory -Force -Path $BackupDir |
    Out-Null

New-Item -ItemType Directory -Force -Path $LogDir |
    Out-Null

function Write-BackupLog {
    param(
        [string]$Level,
        [string]$Message
    )

    $Line = "{0} [{1}] {2}" -f `
        (Get-Date -Format "yyyy-MM-dd HH:mm:ss"),
        $Level,
        $Message

    Add-Content `
        -LiteralPath $script:LogFile `
        -Value $Line `
        -Encoding UTF8

    Write-Output $Line
}

# --------------------------------------------------
# PostgreSQL password-file field escaping
# --------------------------------------------------

function Escape-PgPassField {
    param([string]$Value)

    return $Value.Replace('\', '\\').Replace(':', '\:')
}

# --------------------------------------------------
# Main backup operation
# --------------------------------------------------

try {

    Write-BackupLog "INFO" "StockFlow backup started."

    # Verify PostgreSQL utilities.

    if (-not (Test-Path $PgDump)) {
        throw "pg_dump.exe was not found: $PgDump"
    }

    if (-not (Test-Path $PgRestore)) {
        throw "pg_restore.exe was not found: $PgRestore"
    }

    # Verify saved credential.

    if (-not (Test-Path $CredentialPath)) {
        throw "Backup credential file was not found."
    }

    $Credential = Import-Clixml `
        -LiteralPath $CredentialPath

    if (
        $Credential -isnot [System.Management.Automation.PSCredential] -or
        $Credential.UserName -ne $DbUser
    ) {
        throw "The saved backup credential is invalid."
    }

    $PlainPassword = $Credential.GetNetworkCredential().Password

    if ([string]::IsNullOrEmpty($PlainPassword)) {
        throw "The backup password is empty."
    }

    # Create a temporary PostgreSQL password file.

    $PassFile = Join-Path `
        $env:TEMP `
        ("stockflow-pgpass-" + [guid]::NewGuid().ToString("N"))

    New-Item -ItemType File -Path $PassFile |
        Out-Null

    # Restrict access to the current Windows user
    # and SYSTEM before writing the password.

    $CurrentSid = `
        [System.Security.Principal.WindowsIdentity]::GetCurrent().User

    $SystemSid = `
        [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")

    $Acl = New-Object System.Security.AccessControl.FileSecurity

    $Acl.SetAccessRuleProtection($true, $false)

    $Acl.AddAccessRule(
        [System.Security.AccessControl.FileSystemAccessRule]::new(
            $CurrentSid,
            [System.Security.AccessControl.FileSystemRights]::FullControl,
            [System.Security.AccessControl.AccessControlType]::Allow
        )
    )

    $Acl.AddAccessRule(
        [System.Security.AccessControl.FileSystemAccessRule]::new(
            $SystemSid,
            [System.Security.AccessControl.FileSystemRights]::FullControl,
            [System.Security.AccessControl.AccessControlType]::Allow
        )
    )

    Set-Acl -LiteralPath $PassFile -AclObject $Acl

    $EscapedPassword = Escape-PgPassField $PlainPassword

    $PassLine = "{0}:{1}:{2}:{3}:{4}" -f `
        $DbHost,
        $DbPort,
        $DbName,
        $DbUser,
        $EscapedPassword

    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

    [System.IO.File]::WriteAllText(
        $PassFile,
        $PassLine,
        $Utf8NoBom
    )

    # libpq reads this variable for authentication.

    $env:PGPASSFILE = $PassFile

    # Remove the managed reference to the password.
    # The process may still retain it in memory.

    $PlainPassword = $null
    $EscapedPassword = $null
    $PassLine = $null
    $Credential = $null

    Write-BackupLog "INFO" "Backup credentials loaded."

    # --------------------------------------------------
    # Create PostgreSQL backup
    # --------------------------------------------------

    $DumpArguments = @(
        "--host=$DbHost"
        "--port=$DbPort"
        "--username=$DbUser"
        "--dbname=$DbName"
        "--format=custom"
        "--compress=6"
        "--no-password"
        "--verbose"
        "--file=$PartialBackup"
    )

    Write-BackupLog "INFO" "Running pg_dump."
    # Capture native PostgreSQL stderr in a file.
    # This prevents PowerShell from treating normal pg_dump
    # verbose diagnostics as terminating PowerShell errors.

    $DumpStderrFile = Join-Path `
        $LogDir `
        "pg_dump_$Timestamp.stderr.log"

    # Temporarily allow native PostgreSQL diagnostics.
    $PreviousErrorActionPreference = $ErrorActionPreference

    try {
        $ErrorActionPreference = "Continue"

        & $PgDump @DumpArguments 2> $DumpStderrFile

        # Capture the native exit code immediately.
        $DumpExitCode = $LASTEXITCODE
    }
    finally {
        # Restore the script's original error handling.
        $ErrorActionPreference = $PreviousErrorActionPreference
    }

    # Record PostgreSQL diagnostics in our backup log.
    if (Test-Path -LiteralPath $DumpStderrFile) {

        foreach ($Line in Get-Content -LiteralPath $DumpStderrFile) {
            Write-BackupLog "PG_DUMP" ([string]$Line)
        }

        Remove-Item -LiteralPath $DumpStderrFile -Force
    }

    if ($DumpExitCode -ne 0) {
        throw "pg_dump failed with exit code $DumpExitCode."
    }

    if (-not (Test-Path $PartialBackup)) {
        throw "pg_dump did not create its backup file."
    }

    if ((Get-Item $PartialBackup).Length -le 0) {
        throw "The generated backup is empty."
    }

    # --------------------------------------------------
    # Verify backup archive
    # --------------------------------------------------

    Write-BackupLog "INFO" "Validating PostgreSQL archive."

    $ArchiveOutput = & $PgRestore --list $PartialBackup 2>&1

    $ArchiveExitCode = $LASTEXITCODE

    if ($ArchiveExitCode -ne 0) {
        throw "pg_restore archive validation failed."
    }

    $ArchiveText = $ArchiveOutput -join "`n"

    $RequiredTables = @(
        "alembic_version"
        "login_rate_limits"
        "products"
        "reservations"
        "revoked_tokens"
        "users"
    )

    foreach ($Table in $RequiredTables) {

        $Pattern = "TABLE DATA\s+public\s+" +
            [regex]::Escape($Table) +
            "\s"

        if ($ArchiveText -notmatch $Pattern) {
            throw "Archive is missing table data for $Table."
        }
    }

    Write-BackupLog "INFO" "Archive structure and table data verified."

    # --------------------------------------------------
    # Finalize backup
    # --------------------------------------------------

    Move-Item `
        -LiteralPath $PartialBackup `
        -Destination $FinalBackup `
        -ErrorAction Stop

    $BackupHash = (
        Get-FileHash `
            -LiteralPath $FinalBackup `
            -Algorithm SHA256
    ).Hash

    $ChecksumLine = "{0}  {1}" -f `
        $BackupHash,
        [System.IO.Path]::GetFileName($FinalBackup)

    [System.IO.File]::WriteAllText(
        $ChecksumFile,
        $ChecksumLine + [Environment]::NewLine,
        $Utf8NoBom
    )

    $BackupSize = (Get-Item $FinalBackup).Length

    Write-BackupLog "INFO" "Backup completed successfully."
    Write-BackupLog "INFO" "File: $FinalBackup"
    Write-BackupLog "INFO" "Size: $BackupSize bytes"
    Write-BackupLog "INFO" "SHA256: $BackupHash"

    # --------------------------------------------------
    # Retention: delete only old automated backups
    # --------------------------------------------------

    $RetentionCutoff = (Get-Date).AddDays(-$RetentionDays)

    $OldBackups = Get-ChildItem `
        -LiteralPath $BackupDir `
        -Filter "stockflow_daily_*.dump" `
        -File |
        Where-Object {
            $_.LastWriteTime -lt $RetentionCutoff
        }

    foreach ($OldBackup in $OldBackups) {

        try {

            Remove-Item `
                -LiteralPath $OldBackup.FullName `
                -Force

            $OldChecksum = "$($OldBackup.FullName).sha256"

            if (Test-Path $OldChecksum) {
                Remove-Item -LiteralPath $OldChecksum -Force
            }

            Write-BackupLog "INFO" "Expired backup removed: $($OldBackup.Name)"

        }
        catch {
            Write-BackupLog "WARN" "Could not remove old backup: $($OldBackup.Name). $($_.Exception.Message)"
        }
    }

    Write-BackupLog "INFO" "Retention processing completed."

}
catch {

    $ExitCode = 1

    Write-BackupLog "ERROR" $_.Exception.Message

}
finally {

    # Restore previous environment.

    if ($null -eq $PreviousPgpassFile) {
        Remove-Item Env:PGPASSFILE -ErrorAction SilentlyContinue
    }
    else {
        $env:PGPASSFILE = $PreviousPgpassFile
    }

    # Remove temporary password file.

    if ($PassFile -and (Test-Path $PassFile)) {
        Remove-Item -LiteralPath $PassFile -Force -ErrorAction SilentlyContinue
    }

    # Remove incomplete backup file.

    if ($ExitCode -ne 0 -and (Test-Path $PartialBackup)) {
        Remove-Item -LiteralPath $PartialBackup -Force -ErrorAction SilentlyContinue
    }

}

exit $ExitCode
