"""
Validar APIs habilitadas y acceso a Sheet
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from config.settings import settings

print("""
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║              ⚠️  VALIDACIÓN DE CONFIGURACIÓN DE APIs              ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝

📊 SHEET ID CONFIGURADA:
""")
print(f"  {settings.google_sheet_id}")

print("""
🔑 CREDENCIALES REQUERIDAS:

  Necesitas habilitar DOS APIs en Google Cloud Console:

  1️⃣  GOOGLE SHEETS API
     URL: https://console.developers.google.com/apis/api/sheets.googleapis.com/overview?project=1062678513752
     Estado: ❓ DESCONOCIDO (falta habilitar)
     Click: ENABLE
     Esperar: 2-3 minutos

  2️⃣  GOOGLE DRIVE API  
     URL: https://console.developers.google.com/apis/api/drive.googleapis.com/overview?project=1062678513752
     Estado: ❓ DESCONOCIDO (falta habilitar)
     Click: ENABLE
     Esperar: 2-3 minutos

════════════════════════════════════════════════════════════════════

📁 ARCHIVOS REQUERIDOS:

  ✅ credentials.json
     Estado: """)

if Path('credentials.json').exists():
    print(f"     ✅ PRESENTE (tamaño: {Path('credentials.json').stat().st_size} bytes)")
else:
    print(f"     ❌ FALTA - Descarga desde Google Cloud Console")

print("""
  ✅ token_gmail.json (se crea automáticamente)
     Estado: """)

if Path('token_gmail.json').exists():
    print(f"     ✅ PRESENTE (tamaño: {Path('token_gmail.json').stat().st_size} bytes)")
else:
    print(f"     ⏳ Se creará automáticamente en primer uso")

print("""
════════════════════════════════════════════════════════════════════

✅ CHECKLIST DE HABILITACIÓN:

  [ ] 1. Abre Google Cloud Console
        https://console.cloud.google.com/
  
  [ ] 2. Asegúrate de estar en el proyecto correcto: germanty123-org
  
  [ ] 3. Habilita Google Sheets API
        URL: https://console.developers.google.com/apis/api/sheets.googleapis.com/overview?project=1062678513752
        Click: ENABLE
  
  [ ] 4. Habilita Google Drive API
        URL: https://console.developers.google.com/apis/api/drive.googleapis.com/overview?project=1062678513752
        Click: ENABLE
  
  [ ] 5. Espera 2-3 minutos para que se propague
  
  [ ] 6. Ejecuta de nuevo:
        python test_send_single_email.py

════════════════════════════════════════════════════════════════════

ℹ️  ¿POR QUÉ DOS APIs?

  • Google Sheets API    → Leer/escribir datos en Sheets
  • Google Drive API     → Acceder a archivos de Google Drive
  
  Ambas son necesarias para que funcione correctamente.

════════════════════════════════════════════════════════════════════
""")
