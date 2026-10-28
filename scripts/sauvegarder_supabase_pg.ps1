<#
Exporte les deux bases Supabase avec pg_dump local, sans Docker.
Les identifiants sont résolus par libpq via PGSERVICEFILE + PGPASSFILE
configurés hors du dépôt. Aucun secret n'est lu, inscrit ou affiché ici.
Le contrôle pg_restore --list vérifie la table des matières, pas
une restauration réelle sur base vierge.
#>
[CmdletBinding()]
param(
  [ValidateSet("TEST","PRODUCTION")]
  [string[]] $Environnements = @("TEST","PRODUCTION"),
  [string] $PostgresBin = "",
  [string] $Destination = ""
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($Destination)) {
  $Destination = Join-Path (Split-Path $repo -Parent) "sauvegardes_erp"
}
$destFull = [IO.Path]::GetFullPath($Destination)
$repoFull = [IO.Path]::GetFullPath($repo)
if ($destFull.TrimEnd([IO.Path]::DirectorySeparatorChar) -eq $repoFull.TrimEnd([IO.Path]::DirectorySeparatorChar) -or
    $destFull.StartsWith($repoFull.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar,
                         [StringComparison]::OrdinalIgnoreCase)) {
  throw "Destination interdite : sauvegardes à placer hors du dépôt Git."
}
New-Item -ItemType Directory -Force -Path $destFull | Out-Null

function Outil-PostgreSQL([string]$nom) {
  if (-not [string]::IsNullOrWhiteSpace($PostgresBin)) {
    $cmd = Join-Path $PostgresBin ($nom + ".exe")
    if (-not (Test-Path -LiteralPath $cmd -PathType Leaf)) { throw "$cmd introuvable." }
    return $cmd
  }
  $command = Get-Command $nom -ErrorAction Stop
  return $command.Source
}
$dump = Outil-PostgreSQL "pg_dump"
$restore = Outil-PostgreSQL "pg_restore"

$utc = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")
$manifeste = @()
foreach ($envName in $Environnements) {
  $service = if ($envName -eq "PRODUCTION") { "erp_mortier_prod" } else { "erp_mortier_test" }
  $filename = Join-Path $destFull ("erp_" + $envName.ToLowerInvariant() + "_" + $utc + ".dump")
  Write-Output ("Sauvegarde de " + $envName + " (service libpq : " + $service + ")")
  try {
    & $dump "--dbname=service=$service" "--format=custom" "--file=$filename" "--verbose"
    if ($LASTEXITCODE -ne 0) { throw "pg_dump a échoué : $LASTEXITCODE" }
    if (-not (Test-Path -LiteralPath $filename -PathType Leaf)) { throw "Archive absente" }
    if ((Get-Item -LiteralPath $filename).Length -lt 1024) { throw "Archive anormalement petite" }
    & $restore "--list" $filename | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "pg_restore --list a échoué : $LASTEXITCODE" }
    $hash = (Get-FileHash -LiteralPath $filename -Algorithm SHA256).Hash
    $manifeste += [pscustomobject]@{
      Environnement = $envName
      Fichier = $filename
      TailleOctets = (Get-Item -LiteralPath $filename).Length
      SHA256 = $hash
      Verification = "TOC_LISIBLE_RESTAURATION_NON_TESTEE"
      HorodatageUTC = $utc
    }
  } catch {
    if (Test-Path -LiteralPath $filename -PathType Leaf) {
      Rename-Item -LiteralPath $filename -NewName ((Split-Path $filename -Leaf) + ".INCOMPLET") -ErrorAction SilentlyContinue
    }
    throw
  }
}
$manifestPath = Join-Path $destFull ("manifest_" + $utc + ".json")
$manifeste | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding utf8
Write-Output ("Manifeste sans secrets : " + $manifestPath)
Write-Output "ARCHIVES CRÉÉES ; restaurabilité intégrale NON VÉRIFIÉE."
