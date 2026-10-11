param(
  [Parameter(Mandatory = $true)][string]$ApiUrl,
  [string]$ConfigFile = 'C:\09_IA\sftp\config.env',
  [string]$CertName = '*.us.cloudlogin.co',
  [switch]$SkipBuild
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$dist = Join-Path $root 'frontend\dist'

$cfg = @{}
Get-Content $ConfigFile | Where-Object { $_ -match '^\s*([A-Z_]+)=(.*)$' } | ForEach-Object { $cfg[$matches[1]] = $matches[2].Trim() }
foreach ($k in 'STAGING_HOST', 'STAGING_PORT', 'STAGING_USER', 'STAGING_PASSWORD', 'STAGING_REMOTE_PATH') {
  if (-not $cfg[$k]) { throw "Missing $k in $ConfigFile" }
}

if (-not $SkipBuild) {
  Push-Location (Join-Path $root 'frontend')
  try { npm run build; if ($LASTEXITCODE) { throw 'npm run build failed' } } finally { Pop-Location }
}
[IO.File]::WriteAllText((Join-Path $dist 'config.js'), "window.TAMAGOSHI_API = '$($ApiUrl.TrimEnd('/'))';`n")

# The FTP host serves a shared-hosting wildcard certificate, so the chain must be valid but the name is pinned explicitly.
Add-Type -TypeDefinition @'
using System; using System.Net; using System.Net.Security; using System.Security.Cryptography.X509Certificates;
public static class PinnedCert {
  public static string Name;
  public static bool Check(object s, X509Certificate cert, X509Chain chain, SslPolicyErrors errors) {
    if ((errors & SslPolicyErrors.RemoteCertificateChainErrors) != 0 || cert == null) return false;
    var c = new X509Certificate2(cert);
    return c.GetNameInfo(X509NameType.SimpleName, false) == Name && DateTime.Now < c.NotAfter;
  }
  public static void Install(string name) {
    Name = name;
    ServicePointManager.ServerCertificateValidationCallback = Check;
  }
}
'@
[PinnedCert]::Install($CertName)
$cred = New-Object Net.NetworkCredential($cfg.STAGING_USER, $cfg.STAGING_PASSWORD)
$base = "ftp://$($cfg.STAGING_HOST):$($cfg.STAGING_PORT)$($cfg.STAGING_REMOTE_PATH.TrimEnd('/'))"

function Invoke-Ftp([string]$uri, [string]$method, [string]$upload) {
  $req = [Net.FtpWebRequest]::Create($uri)
  $req.Method = $method; $req.Credentials = $cred; $req.EnableSsl = $true; $req.UsePassive = $true; $req.KeepAlive = $false
  if ($upload) {
    $bytes = [IO.File]::ReadAllBytes($upload)
    $req.ContentLength = $bytes.Length
    $s = $req.GetRequestStream(); $s.Write($bytes, 0, $bytes.Length); $s.Close()
  }
  $res = $req.GetResponse()
  $reader = New-Object IO.StreamReader($res.GetResponseStream())
  $body = $reader.ReadToEnd(); $reader.Close(); $res.Close()
  $body
}
function Get-RemoteList([string]$path) {
  (Invoke-Ftp "$base$path/" ([Net.WebRequestMethods+Ftp]::ListDirectoryDetails)) -split "`r?`n" | Where-Object { $_ }
}
function Backup-Remote([string]$path, [string]$target) {
  New-Item -ItemType Directory -Force $target | Out-Null
  foreach ($line in Get-RemoteList $path) {
    $name = ($line -split '\s+', 9)[8]
    if (-not $name -or $name -in '.', '..') { continue }
    if ($line.StartsWith('d')) { Backup-Remote "$path/$name" (Join-Path $target $name) }
    else {
      $req = [Net.FtpWebRequest]::Create("$base$path/$name")
      $req.Method = [Net.WebRequestMethods+Ftp]::DownloadFile; $req.Credentials = $cred; $req.EnableSsl = $true; $req.UseBinary = $true
      $res = $req.GetResponse(); $out = [IO.File]::Create((Join-Path $target $name)); $res.GetResponseStream().CopyTo($out); $out.Close(); $res.Close()
    }
  }
}

$existing = Get-RemoteList ''
Write-Host "Remote entries before deploy: $($existing.Count)"
if ($cfg.DEPLOY_BACKUP_BEFORE_UPLOAD -eq 'true' -and $existing.Count) {
  $backup = Join-Path $root ("deploy-backups\staging-" + (Get-Date -Format 'yyyyMMdd_HHmmss'))
  Backup-Remote '' $backup
  Write-Host "Backup saved to $backup"
}

$dirs = Get-ChildItem $dist -Recurse -Directory | ForEach-Object { $_.FullName.Substring($dist.Length).Replace('\', '/') }
foreach ($d in $dirs) { try { Invoke-Ftp "$base$d" ([Net.WebRequestMethods+Ftp]::MakeDirectory) | Out-Null } catch {} }
# index.html last, so it never references assets that are not uploaded yet.
$files = Get-ChildItem $dist -Recurse -File | Sort-Object { $_.Name -eq 'index.html' }
foreach ($f in $files) {
  $rel = $f.FullName.Substring($dist.Length).Replace('\', '/')
  Invoke-Ftp "$base$rel" ([Net.WebRequestMethods+Ftp]::UploadFile) $f.FullName | Out-Null
  Write-Host "uploaded $rel"
}
Write-Host "Deployed to $($cfg.STAGING_URL) with API $ApiUrl"
