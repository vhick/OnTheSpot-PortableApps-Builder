param([Parameter(Mandatory=$true)][string]$Source,
      [Parameter(Mandatory=$true)][string]$Stage,
      [Parameter(Mandatory=$true)][string]$Identity)
$ErrorActionPreference='Stop'
$info=Get-Content -Raw -LiteralPath $Identity | ConvertFrom-Json
$pythonVersion=[string]$info.python_version
$nodeMajor=[int]$info.node_major
$uvVersion=[string]$info.uv_version
Write-Host "Building release $($info.upstream_version), Python $pythonVersion, Node $nodeMajor, uv $uvVersion"
$dest=Join-Path $Stage 'App\OnTheSpot'
$runtime=Join-Path $dest 'runtime'
$code=Join-Path $dest 'code\onthespot'
$ui=Join-Path $dest 'ui'
New-Item -ItemType Directory -Force -Path $runtime,$code,$ui | Out-Null
# Managed uv Python distributions are self-contained, unlike venv Python redirectors.
& uv python install $pythonVersion
if ($LASTEXITCODE -ne 0) { throw 'MANAGED_PYTHON_ACQUIRE_FAILED' }
$python=(& uv python find --managed-python $pythonVersion | Select-Object -Last 1).Trim()
if (!$python -or !(Test-Path -LiteralPath $python)) { throw 'MANAGED_PYTHON_NOT_FOUND' }
$actual = (& $python -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")' | Select-Object -Last 1).Trim()
if ($actual -ne $pythonVersion) { throw "PYTHON_VERSION_MISMATCH: expected $pythonVersion got $actual" }
$parent=Split-Path -Parent $python
Copy-Item -Path (Join-Path $parent '*') -Destination $runtime -Recurse -Force -ErrorAction Stop
if (!(Test-Path (Join-Path $runtime 'python.exe'))) { throw 'EMBEDDED_PYTHON_COPY_FAILED' }
# uv honors the precise upstream lock. No unpinned pip dependency upgrades.
& uv sync --project (Join-Path $Source 'api') --frozen --no-dev --no-install-project --python $python
if ($LASTEXITCODE -ne 0) { throw 'UPSTREAM_LOCKED_DEPENDENCY_INSTALL_FAILED' }
$site=Join-Path $Source 'api\.venv\Lib\site-packages'
if (!(Test-Path -LiteralPath $site)) { throw "UPSTREAM_VENV_SITE_PACKAGES_MISSING: $site" }
New-Item -Force -ItemType Directory -Path (Join-Path $runtime 'Lib\site-packages') | Out-Null
Copy-Item -Path (Join-Path $site '*') -Destination (Join-Path $runtime 'Lib\site-packages') -Recurse -Force
# Include actual upstream application files and package resources, not only .py files.
Copy-Item -Path (Join-Path $Source 'api\src\onthespot\*') -Destination $code -Recurse -Force
# Build UI with upstream's package-lock; do not run npm audit as a postinstall write.
Push-Location (Join-Path $Source 'ui')
try {
    & npm ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'NPM_CI_FAILED' }
    & npm run build
    if ($LASTEXITCODE -ne 0) { throw 'REACT_BUILD_FAILED' }
} finally { Pop-Location }
if (!(Test-Path (Join-Path $Source 'ui\dist\index.html'))) { throw 'REACT_BUILD_MISSING_INDEX' }
Copy-Item -Path (Join-Path $Source 'ui\dist\*') -Destination $ui -Force -Recurse
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'portable_bootstrap.py') -Destination (Join-Path $dest 'portable_bootstrap.py')
# Avoid shipping .venv, node_modules, or Python build caches in distributable package.
Write-Host 'Staged Python+FastAPI runtime and React UI'
