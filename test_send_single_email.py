"""
Script para enviar email de prueba a UNO de los leads
y verificar que se registre como "Enviado" en Sheets
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from core.sheets_client import SheetsClient
from services.gmail_service import GmailService
from services.gemini_service import GeminiService
from core.models import Email, SendStatus
from config.settings import Settings


async def main():
    """Envía email a uno de los leads"""
    print("=" * 70)
    print("🚀 PRUEBA DE EMAIL - Enviar a UN lead")
    print("=" * 70)
    
    try:
        # Cargar configuración
        settings = Settings()
        
        # Inicializar servicios
        sheets = SheetsClient(credentials_file='credentials.json')
        gmail = GmailService('credentials.json', 'token_gmail.json')
        gemini = GeminiService()
        
        # PASO 1: Leer leads de la Sheet
        print("\n📋 Paso 1: Leyendo leads de tu Google Sheet...")
        leads = sheets.get_all_leads()
        
        if not leads:
            print("❌ No hay leads en la Sheet")
            return
        
        print(f"✅ Encontrados {len(leads)} leads")
        
        # PASO 2: Encontrar el PRIMERO que no tenga email enviado
        print("\n📧 Paso 2: Buscando lead SIN email enviado...")
        target_lead = None
        for lead in leads:
            # Si el lead no tiene estado "Enviado", es candidato
            if lead.send_status != SendStatus.SENT.value:
                target_lead = lead
                break
        
        if not target_lead:
            print("❌ Todos los leads ya recibieron email")
            print("\n📊 Leads actuales:")
            for i, lead in enumerate(leads[:10], 1):
                print(f"{i}. {lead.contact_name} ({lead.contact_email}) - {lead.send_status}")
            return
        
        print(f"✅ Lead seleccionado: {target_lead.contact_name}")
        print(f"   📧 Email: {target_lead.contact_email}")
        print(f"   🏢 Empresa: {target_lead.business_name}")
        print(f"   📍 Rubro: {target_lead.industry}")
        
        # PASO 3: Generar email personalizado
        print("\n✉️  Paso 3: Generando email personalizado...")
        email_body = gemini.generate_email_for_lead(
            lead_name=target_lead.contact_name,
            business_name=target_lead.business_name,
            industry=target_lead.industry,
            specific_note=target_lead.notes or "",
            template="pymes" if "pyme" in target_lead.industry.lower() else "marketing"
        )
        
        print("✅ Email generado")
        
        # PASO 4: Crear objeto Email
        email = Email(
            to=target_lead.contact_email,
            subject="🚀 Developer Freelance - Desarrollo Web",
            body=email_body
        )
        
        # PASO 5: Enviar por Gmail
        print("\n🚀 Paso 4: Enviando email por Gmail...")
        message_id = gmail.send_email(email)
        print(f"✅ Email enviado exitosamente!")
        print(f"   📨 Message ID: {message_id}")
        
        # PASO 6: Registrar en Sheets como "Enviado"
        print("\n💾 Paso 5: Registrando en Google Sheets como 'Enviado'...")
        sheets.update_send_status(
            lead_email=target_lead.contact_email,
            status=SendStatus.SENT,
            message_id=message_id
        )
        print("✅ Estado actualizado en Sheets")
        
        # PASO 7: Mostrar resumen
        print("\n" + "=" * 70)
        print("📊 RESUMEN DEL ENVÍO:")
        print("=" * 70)
        print(f"✅ Destinatario: {target_lead.contact_name}")
        print(f"✅ Email: {target_lead.contact_email}")
        print(f"✅ Empresa: {target_lead.business_name}")
        print(f"✅ Asunto: 🚀 Developer Freelance - Desarrollo Web")
        print(f"✅ Estado en Sheets: ENVIADO")
        print(f"✅ Gmail Message ID: {message_id}")
        print("\n🎉 ¡Email enviado y registrado correctamente!")
        print("=" * 70)
        
        # PASO 8: Mostrar preview del email
        print("\n📝 PREVIEW DEL EMAIL ENVIADO:")
        print("=" * 70)
        print(email_body)
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
