<#
E2E Test Script (PowerShell)
Location: scripts/e2e_test.ps1
Objetivo: crear checkout -> trigger webhook (Stripe CLI o simulado) -> esperar -> leer logs -> activar licencia local -> ejecutar convertir -> validar out.json

USO:
  1) Colocar este archivo en C:\Users\Eche\proyectos\logpattern_converter\scripts\e2e_test.ps1
  2) Abrir PowerShell en la carpeta raíz del repo: C:\Users\Eche\proyectos\logpattern_converter
  3) Ejecutar: .\scripts\e2e_test.ps1
  4) Requiere: gcloud (autenticado), python en PATH. Opcional: stripe CLI para trigger real.

Notas:
  - El script intenta usar STRIPE CLI si está disponible; si no, hace un POST simulado al webhook público.
  - No imprime secretos. Ajusta las variables al principio si necesitas cambiar endpoints/price.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ------------------ CONFIG (ajusta si hace falta) ------------------
$PROJECT       = "logpattern-pro-999c8"
# Puedes sobrescribir estas URLs con variables de entorno si lo prefieres:
$CREATE_CHECKOUT_URL = if ($env:CREATE_CHECKOUT_URL) { $env:CREATE_CHECKOUT_URL } else { "https://createcheckoutsession-62426013358.us-central1.run.app" }
$WEBHOOK_URL          = if ($env:STRIPE_WEBHOOK_FORWARD_URL) { $env:STRIPE_WEBHOOK_FORWARD_URL } else { "https://us-central1-logpattern-pro-999c8.cloudfunctions.net/stripeWebhook" }

$REPO_ROOT     = (Get-Location).Path
$PRICE_ID      = if ($env:PRICE_ID) { $env:PRICE_ID } else { "price_1ScsVLGUoPKCRMIeleKI4zbm" }

# Paths / fixtures
$PATTERNS_FILE = "patterns_test.txt"
$INPUT_FILE    = "input_test.log"
$EXPECTED_OUT  = "out.json"

# ------------------ HELPERS ------------------
function Log($msg) {
  Write-Output "$(Get-Date -Format u) | $msg"
}

function Http-PostJson($url, $obj, $timeoutSec=30) {
  $body = $obj | ConvertTo-Json -Depth 8
  return Invoke-RestMethod -Method Post -Uri $url -Body $body -ContentType "application/json" -TimeoutSec $timeoutSec -ErrorAction Stop
}

# ------------------ START ------------------
Log "=== E2E: Start ==="

# ------------------ 1) Create Checkout Session (call function) ------------------
Log "STEP 1: Create Checkout Session -> $CREATE_CHECKOUT_URL"

$payloadCreate = @{
  priceId = $PRICE_ID
  customer_email = "e2e-test+$(Get-Random)@example.com"
  success_url = "https://example.com/success"
  cancel_url = "https://example.com/cancel"
  metadata = @{ test = "e2e" }
}

try {
  $resp = Http-PostJson -url $CREATE_CHECKOUT_URL -obj $payloadCreate -timeoutSec 20
  Log "createCheckoutSession response (trim):"
  $trim = ($resp | ConvertTo-Json -Depth 4)
  Log $trim
  # Try to extract session id robustly
  if ($resp -is [System.Management.Automation.PSCustomObject]) {
    if ($resp.id) { $sessionId = $resp.id }
    elseif ($resp.sessionId) { $sessionId = $resp.sessionId }
  }
  if (-not $sessionId) { $sessionId = "cs_sim_$(Get-Random)" ; Log "No sessionId returned; using fallback: $sessionId" }
} catch {
  Log "ERROR: createCheckoutSession failed: $($_.Exception.Message)"
  throw $_
}

# ------------------ 2) Trigger webhook (Stripe CLI if available) ------------------
Log "STEP 2: Trigger webhook (Stripe CLI preferred, fallback simulated POST)"
$useStripeCLI = $false
if (Get-Command stripe -ErrorAction SilentlyContinue) { $useStripeCLI = $true }

if ($useStripeCLI) {
  Log "Stripe CLI detected. Running fixture trigger..."
  try {
    # Use stripe trigger; this may use built-in fixtures and forward via stripe listen
    $triggerOut = & stripe trigger checkout.session.completed --session $sessionId --api-key $env:STRIPE_TEST_KEY 2>&1
    Log "stripe trigger output (trim):"
    $triggerOut | ForEach-Object { Log $_ }
  } catch {
    Log "Stripe CLI trigger failed or not authenticated: $($_.Exception.Message). Falling back to simulated POST."
    $useStripeCLI = $false
  }
}

if (-not $useStripeCLI) {
  Log "Sending simulated webhook POST to $WEBHOOK_URL (safe test payload)."
  $payload = @{
    id = $sessionId
    object = "checkout.session"
    payment_status = "paid"
    customer_email = $payloadCreate.customer_email
    metadata = $payloadCreate.metadata
    data = @{ object = @{ id = $sessionId; payment_status = "paid"; customer_email = $payloadCreate.customer_email; metadata = $payloadCreate.metadata } }
  }
  try {
    $r = Invoke-RestMethod -Method Post -Uri $WEBHOOK_URL -Body ($payload | ConvertTo-Json -Depth 8) -ContentType "application/json" -TimeoutSec 20 -ErrorAction Stop
    Log "Webhook POST returned (if any): $($r | ConvertTo-Json -Depth 3)"
  } catch {
    Log "Webhook POST returned non-2xx or had no body: $($_.Exception.Message)"
    # continue — webhook may still have been invoked
  }
}

# ------------------ 3) Poll logs / Firestore for license LP-... ------------------
Log "STEP 3: Polling logs / Firestore for license (LP-...)"

# Function to search LP- keys in an array of lines
function Find-License-InLines($lines) {
  foreach ($ln in $lines) {
    if ($ln -match "(LP-[0-9A-Fa-f]{4,})") {
      return $matches[1]
    }
  }
  return $null
}

$license = $null
$maxAttempts = 12
$attempt = 0
while (($attempt -lt $maxAttempts) -and (-not $license)) {
  $attempt++
  Log "Logs poll attempt $attempt/$maxAttempts ..."
  try {
    # Read the last 200 log lines for the function (plain text)
    $raw = & gcloud functions logs read stripeWebhook --project=$PROJECT --limit=200 2>&1
    # $raw is an array of strings; search for common messages
    $license = Find-License-InLines -lines $raw
    if (-not $license) {
      # Some deployments log "License created:" or "License generated:" — also look for those exact phrases
      foreach ($l in $raw) {
        if ($l -match "License created:\s*(LP-[0-9A-Fa-f]{4,})") { $license = $matches[1]; break }
        if ($l -match "License generated:\s*(LP-[0-9A-Fa-f]{4,})") { $license = $matches[1]; break }
        if ($l -match "License key:\s*(LP-[0-9A-Fa-f]{4,})") { $license = $matches[1]; break }
      }
    }
  } catch {
    Log "gcloud logs read failed (attempt $attempt): $($_.Exception.Message)"
  }

  if ($license) { break }
  Start-Sleep -Seconds 5
}

if (-not $license) {
  Log "No license found after polling logs. Attempting Firestore direct read (requires gcloud/auth and python google-cloud-firestore)."
  try {
    # try a quick python snippet to query Firestore for latest license doc id
    $py = @"
import os, sys, datetime
from google.cloud import firestore
p = os.environ.get('PROJECT') or os.environ.get('FIREBASE_PROJECT')
if not p:
    print('NO_PROJECT')
    sys.exit(2)
db = firestore.Client(project=p)
docs = list(db.collection('licenses').order_by('creationDate', direction=firestore.Query.DESCENDING).limit(5).stream())
for d in docs:
    data = d.to_dict()
    # print key and doc data summary
    print(d.id)
    if isinstance(data, dict) and 'activated' in data:
        print('FOUND_DOC')
        sys.exit(0)
print('NO_LICENSES')
sys.exit(3)
"@
    $pyFile = Join-Path $env:TEMP "e2e_check_fs.py"
    $py | Out-File -FilePath $pyFile -Encoding utf8
    $env:PROJECT = $PROJECT
    $pyOut = & python $pyFile 2>&1
    Log "Firestore python check output:"
    $pyOut | ForEach-Object { Log $_ }
    if ($pyOut -match "FOUND_DOC") {
      # first line printed by script is doc id
      $first = ($pyOut -split "`n")[0].Trim()
      if ($first -match "LP-[0-9A-Fa-f]{4,}") { $license = $first }
    }
  } catch {
    Log "Firestore check failed: $($_.Exception.Message)"
  }
}

if (-not $license) {
  Log "E2E ABORT: No license detected. Inspect function logs in console or run gcloud logs read manually."
  exit 1
}

Log "Found license: $license"

# ------------------ 4) Create venv, install package, activate license, run convert ------------------
Log "STEP 4: Create ephemeral venv, install package and run CLI actions"

Push-Location $REPO_ROOT

$venvDir = Join-Path $REPO_ROOT "e2e_venv"
if (Test-Path $venvDir) {
  Remove-Item -Recurse -Force $venvDir
}
python -m venv $venvDir
$activate = Join-Path $venvDir "Scripts\Activate.ps1"
if (-not (Test-Path $activate)) { Log "Venv activate script not found at $activate"; exit 1 }
& $activate

Log "Python in venv: $(python --version)"

# Upgrade pip and install requirements if any
python -m pip install --upgrade pip setuptools wheel
if (Test-Path "$REPO_ROOT\requirements.txt") {
  python -m pip install -r "$REPO_ROOT\requirements.txt"
}

# Install package in editable mode (to expose CLI)
python -m pip install -e "$REPO_ROOT" | ForEach-Object { Log $_ }

# Ensure fixture files exist
if (-not (Test-Path $PATTERNS_FILE)) {
  @"
TIMESTAMP \[LEVEL\] MESSAGE
"@ | Out-File -FilePath $PATTERNS_FILE -Encoding utf8
}
if (-not (Test-Path $INPUT_FILE)) {
  @"
2025-12-11 07:00:00 [INFO] Servicio iniciado
2025-12-11 07:01:00 [ERROR] Falló la conexión a DB
"@ | Out-File -FilePath $INPUT_FILE -Encoding utf8
}

# Activation: try python -m first, fallback to 'logconv'
Log "Activating license via CLI: $license"
$activated = $false
try {
  Log "Attempting: python -m logpattern_converter activar $license"
  & python -m logpattern_converter activar $license 2>&1 | ForEach-Object { Log $_ }
  $activated = $true
} catch {
  Log "python -m activation failed: $($_.Exception.Message)"
  if (Get-Command logconv -ErrorAction SilentlyContinue) {
    try {
      Log "Attempting: logconv activar $license"
      & logconv activar $license 2>&1 | ForEach-Object { Log $_ }
      $activated = $true
    } catch {
      Log "logconv activation failed: $($_.Exception.Message)"
    }
  }
}

if (-not $activated) {
  Log "Activation failed. Aborting."
  exit 1
}

# Run conversion: try python -m, then logconv, allow output path flag or positional
Log "Running conversion to $EXPECTED_OUT"
$converted = $false
try {
  Log "Trying: python -m logpattern_converter convertir $PATTERNS_FILE $INPUT_FILE"
  & python -m logpattern_converter convertir $PATTERNS_FILE $INPUT_FILE 2>&1 | ForEach-Object { Log $_ }
  $converted = $true
} catch {
  Log "python -m convertir failed: $($_.Exception.Message)"
  if (Get-Command logconv -ErrorAction SilentlyContinue) {
    try {
      Log "Trying: logconv convertir $PATTERNS_FILE $INPUT_FILE -o $EXPECTED_OUT"
      & logconv convertir $PATTERNS_FILE $INPUT_FILE -o $EXPECTED_OUT 2>&1 | ForEach-Object { Log $_ }
      $converted = $true
    } catch {
      Log "logconv convertir failed: $($_.Exception.Message)"
    }
  }
}

if (-not $converted) {
  Log "Conversion failed. Aborting."
  exit 1
}

# ------------------ 5) Validate out.json ------------------
if (Test-Path $EXPECTED_OUT) {
  $out = Get-Content $EXPECTED_OUT -Raw
  Log "=== E2E SUCCESS: out.json exists (length: $($out.Length) chars) ==="
  Write-Output ($out.Substring(0,[Math]::Min(600,$out.Length)))
  Log "E2E PASSED. Please commit scripts/e2e_test.ps1 to repo for repeatable runs."
  Pop-Location
  exit 0
} else {
  Log "E2E FAILED: $EXPECTED_OUT not found. Inspect logs above."
  Pop-Location
  exit 1
}
