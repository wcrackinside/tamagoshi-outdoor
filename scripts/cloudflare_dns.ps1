param(
  [string]$Zone = 'privantix.io',
  [string]$Name = 'outdoor-staging.privantix.io',
  [string]$Ip = '162.210.96.115',
  [string]$ConfigFile = 'C:\09_IA\sftp\config.env',
  [bool]$Proxied = $true
)
$ErrorActionPreference = 'Stop'
$token = (Get-Content $ConfigFile | Where-Object { $_ -match '^\s*CLOUDFLARE_API_TOKEN=' }) -replace '^\s*CLOUDFLARE_API_TOKEN=', ''
if (-not $token) { throw "Add CLOUDFLARE_API_TOKEN=... to $ConfigFile (token with Zone.DNS:Edit on $Zone)" }
$h = @{ Authorization = "Bearer $($token.Trim())" }
$api = 'https://api.cloudflare.com/client/v4'

$zoneId = (Invoke-RestMethod "$api/zones?name=$Zone" -Headers $h).result[0].id
if (-not $zoneId) { throw "Token cannot see zone $Zone" }
$body = @{ type = 'A'; name = $Name; content = $Ip; ttl = 1; proxied = $Proxied } | ConvertTo-Json
$existing = (Invoke-RestMethod "$api/zones/$zoneId/dns_records?name=$Name" -Headers $h).result
if ($existing) {
  $r = Invoke-RestMethod "$api/zones/$zoneId/dns_records/$($existing[0].id)" -Method Put -Headers $h -Body $body -ContentType 'application/json'
  "updated $($existing[0].type) record -> $($r.result.type) $($r.result.name) $($r.result.content) proxied=$($r.result.proxied)"
} else {
  $r = Invoke-RestMethod "$api/zones/$zoneId/dns_records" -Method Post -Headers $h -Body $body -ContentType 'application/json'
  "created $($r.result.type) $($r.result.name) $($r.result.content) proxied=$($r.result.proxied)"
}
