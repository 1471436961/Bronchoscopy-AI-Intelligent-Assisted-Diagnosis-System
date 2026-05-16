$env:PYTHONDONTWRITEBYTECODE='1'
$env:MODEL_PATH=''
$env:PYTHONPATH='E:\Bronchoscopy-AI-Intelligent-Assisted-Diagnosis-System;E:\Bronchoscopy-AI-Intelligent-Assisted-Diagnosis-System\inference;E:\Bronchoscopy-AI-Intelligent-Assisted-Diagnosis-System\backend\generated'
Set-Location 'E:\Bronchoscopy-AI-Intelligent-Assisted-Diagnosis-System'
& 'E:\Bronchoscopy-AI-Intelligent-Assisted-Diagnosis-System\.venv-1\Scripts\python.exe' -m app.server
