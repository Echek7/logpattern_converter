Write-Host "`n=== BUSCANDO PYTHON ===`n"
$cmd = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
  Write-Host "Usando: py"
  $cmd = { py -3 -m pytest -q }
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
  Write-Host "Usando: python"
  $cmd = { python -m pytest -q }
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
  Write-Host "Usando: python3"
  $cmd = { python3 -m pytest -q }
} else {
  Write-Host "❌ No se encontró Python en PATH."
  Write-Host "➡ Instálalo desde https://www.python.org/downloads/ y marca 'Add to PATH'"
  exit 1
}

Write-Host "`n=== EJECUTANDO PYTEST (últimas 120 líneas) ===`n"
# Ejecuta y muestra las últimas 120 líneas para que tengas contexto
& $cmd 2>&1 | Select-Object -Last 120

Write-Host "`n=== FIN ===`n"
Read-Host "Presiona ENTER para cerrar esta ventana"
