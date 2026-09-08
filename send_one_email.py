"""
Script para enviar email a UN lead que no ha recibido email aún.
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from core.sheets_client import SheetsClient
from services.gemini_service import GeminiService
from services.gmail_service import GmailService
from core.models import Email

def find_unsent_lead():
    """Busca el primer lead que no tiene email enviado"""
    sheets = SheetsClient('credentials.json', 'token_gmail.json')
    
    # Leer todos los leads
    leads = sheets.get_all_leads()
    
    print("📋 Buscando leads sin email enviado...\n")
    
    for i, lead in enumerate(leads, start=2):  # Start en 2 porque fila 1 es header
        # Verificar si el email ya fue enviado
        sent_date = lead.get('sent_date', '')
        sent_status = lead.get('sent_status', '')
        
        # Si columna A (sent_date) está vacía, no se ha enviado
        if not sent_date or sent_date.strip() == '':
            print(f"✅ Lead sin enviar encontrado en fila {i}:")
            print(f"   Nombre: {lead.get('business_name', 'N/A')}")
            print(f"   Email: {lead.get('email', 'N/A')}")
            print(f"   Track: {lead.get('track', 'N/A')}")
            print()
            return i, lead
    
    print("❌ No hay leads sin enviar")
    return None, None

def send_email_to_lead(row_number, lead):
    """Envía email a un lead específico"""
    
    gemini = GeminiService()
    gmail = GmailService('credentials.json', 'token_gmail.json')
    sheets = SheetsClient('credentials.json', 'token_gmail.json')
    
    # Extraer datos del lead
    lead_name = lead.get('contact_name', lead.get('business_name', 'Contacto'))
    email_to = lead.get('email', '')
    business_name = lead.get('business_name', '')
    
    if not email_to:
        print("❌ Error: No hay email para este lead")
        return False
    
    print("=" * 70)
    print(f"📧 ENVIANDO EMAIL A: {lead_name} ({email_to})")
    print("=" * 70)
    
    # 1. Generar email
    print("\n1️⃣  Generando email...")
    body = gemini.generate_email_for_lead(
        lead_name=lead_name,
        business_name=business_name,
        industry='Marketing',
        specific_note='',
        template='marketing'
    )
    
    print("✅ Email generado")
    print("\n📝 Contenido del email:")
    print("-" * 70)
    print(body)
    print("-" * 70)
    
    # 2. Crear objeto Email
    email_obj = Email(
        to=email_to,
        subject="Developer freelance",
        body=body
    )
    
    # 3. Enviar email
    print("\n2️⃣  Enviando email...")
    try:
        message_id = gmail.send_email(email_obj)
        print(f"✅ Email enviado correctamente")
        print(f"   Message ID: {message_id}")
        
        # 4. Actualizar Google Sheets
        print("\n3️⃣  Actualizando Google Sheets...")
        
        # Actualizar fecha de envío (columna A) y estado (columna K)
        today = datetime.now().strftime("%d/%m/%Y")
        sheets.update_send_status(row_number, "Enviado", message_id)
        
        print(f"✅ Fila {row_number} actualizada:")
        print(f"   Fecha envío: {today}")
        print(f"   Estado: Enviado")
        print(f"   Message ID: {message_id}")
        
        print("\n" + "=" * 70)
        print("✅ ¡EMAIL ENVIADO CON ÉXITO!")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"❌ Error al enviar: {e}")
        return False

def main():
    print("\n" + "=" * 70)
    print("🚀 SISTEMA DE ENVÍO DE EMAILS - SEND SINGLE EMAIL")
    print("=" * 70)
    
    # Buscar lead sin enviar
    row_number, lead = find_unsent_lead()
    
    if not lead:
        print("\n💡 Sugerencia: Hay que agregar más leads a la planilla")
        sys.exit(1)
    
    # Enviar email
    success = send_email_to_lead(row_number, lead)
    
    if success:
        print("\n📌 Próximos pasos:")
        print("   1. Revisar el email en tu Gmail Enviados")
        print("   2. Esperar respuestas")
        print("   3. Ejecutar nuevamente para enviar más emails")
        sys.exit(0)
    else:
        print("\n❌ Error al enviar email")
        sys.exit(1)

if __name__ == "__main__":
    main()
