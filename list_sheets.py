"""
Script para listar todas las hojas de tu Google Sheet.
Útil para verificar los nombres exactos de las hojas.
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def list_sheets():
    """Lista todas las hojas del Sheet"""
    
    sheet_id = "1hjwAUrKaCu53McleYaJZj99b65IoKHBVqIZ96qfvF1I"
    creds = None
    
    # Cargar credenciales
    if Path("token.json").exists():
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    
    # Conectar a Sheets API
    service = build("sheets", "v4", credentials=creds)
    
    # Obtener info del Sheet
    print("\n" + "=" * 70)
    print("📋 LISTANDO TODAS LAS HOJAS DE TU SPREADSHEET")
    print("=" * 70)
    
    try:
        sheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        
        print(f"\n📊 Nombre del Spreadsheet: {sheet['properties']['title']}")
        print(f"ID: {sheet_id}\n")
        
        print("Hojas disponibles:")
        print("-" * 70)
        
        for i, s in enumerate(sheet['sheets'], 1):
            name = s['properties']['title']
            sheet_id_actual = s['properties']['sheetId']
            grid = s['properties'].get('gridProperties', {})
            rows = grid.get('rowCount', 'N/A')
            cols = grid.get('columnCount', 'N/A')
            
            print(f"\n{i}. '{name}'")
            print(f"   Sheet ID (gid): {sheet_id_actual}")
            print(f"   Filas: {rows} | Columnas: {cols}")
            print(f"   Rango para settings.py: '{name}!A1:L1000'")
        
        print("\n" + "=" * 70)
        print("📌 USAR EL NOMBRE EXACTO DE LA HOJA EN settings.py")
        print("=" * 70 + "\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    list_sheets()
