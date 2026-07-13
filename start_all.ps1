# start_all.ps1 - Start all parts of the Rising_water project on Windows
# Usage: run from project root in PowerShell: .\start_all.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

# Create and install Python venv if missing
if (-not (Test-Path "$root\venv")) {
    Write-Host "Creating Python virtualenv..."
    python -m venv venv
    Write-Host "Activating venv and installing Python requirements (this may take a while)..."
    & "$root\venv\Scripts\Activate"
    pip install -r requirements.txt
} else {
    Write-Host "Using existing virtualenv."
}

# Start Flask app (port 5000)
Write-Host "Starting Flask app on port 5000 in a new window..."
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root'; & '$root\\venv\\Scripts\\Activate'; python app.py"

# Start Node backend on port 5001 to avoid conflict with Flask
Write-Host "Starting Node backend on port 5001 in a new window..."
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root\\backend'; $env:PORT=5001; npm start"

# Start React frontend
Write-Host "Starting React frontend in a new window..."
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root\\frontend'; npm start"

# Start Streamlit (optional) in a new window
Write-Host "Starting Streamlit app in a new window (optional)..."
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root'; & '$root\\venv\\Scripts\\Activate'; streamlit run streamlit_app.py"

Write-Host "All start commands issued. Check the new windows for logs and errors."
