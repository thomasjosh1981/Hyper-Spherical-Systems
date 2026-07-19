param(
    [string]$ModelUrl = "https://huggingface.co/bartowski/gemma-2-9b-it-GGUF/resolve/main/gemma-2-9b-it-Q4_K_M.gguf",
    [string]$OutputDir = "models",
    [string]$FileName = "gemma-2-9b-it-uncensored-brain.gguf"
)

Write-Host "=== Fetching Local Recursive Supervisor Brain ==="
Write-Host "Target: Gemma 2 9B (Unaligned / Raw IT Base)"

if (-Not (Test-Path -Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

$Destination = Join-Path -Path $OutputDir -ChildPath $FileName

Write-Host "Downloading model to $Destination..."
Write-Host "This is a large file (~6-8GB) and may take several minutes depending on your connection."

Invoke-WebRequest -Uri $ModelUrl -OutFile $Destination -UseBasicParsing

if (Test-Path $Destination) {
    Write-Host "[SUCCESS] Supervisor Brain successfully downloaded and staged!"
    Write-Host "You can now spin this model through golden_candy_spinner to use it as the autonomous optimizer."
} else {
    Write-Host "[ERROR] Failed to download the model."
}
