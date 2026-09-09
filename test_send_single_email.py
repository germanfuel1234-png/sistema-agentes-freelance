"""
Script para enviar email de prueba a UNO de los leads
y verificar que se registre como "Enviado" en Sheets
"""
import asyncio
import sys
import os
from datetime import datetime

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
            # Debe estar pendiente y tener un email de verdad (no un
            # handle de Instagram ni un link a formulario de contacto,
            # que también terminan en la columna "Mail o IG")
            has_valid_email = bool(
                lead.email
                and "@" in lead.email
                and "IG @" not in lead.email
                and "Formulario" not in lead.email
            )
            if lead.send_status != SendStatus.SENT and has_valid_email:
                target_lead = lead
                break

        if not target_lead:
            print("❌ No hay leads pendientes con email válido")
            print("\n📊 Leads actuales:")
            for i, lead in enumerate(leads[:10], 1):
                print(f"{i}. {lead.contact_name} ({lead.email}) - {lead.send_status.value}")
            return
        
        print(f"✅ Lead seleccionado: {target_lead.contact_name}")
        print(f"   📧 Email: {target_lead.email}")
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
            to=target_lead.email,
            subject="Developer freelance",
            body=email_body
        )
        
        # PASO 5: Enviar por Gmail
        print("\n🚀 Paso 4: Enviando email por Gmail...")
        message_id = gmail.send_email(email)
        if not message_id:
            print("❌ No se obtuvo Message ID de Gmail. El envío pudo haber fallado.")
            return
        print(f"✅ Email enviado exitosamente!")
        print(f"   📨 Message ID: {message_id}")
        
        # PASO 6: Registrar en Sheets como "Enviado"
        print("\n💾 Paso 5: Registrando en Google Sheets como 'Enviado'...")
        if not target_lead.id:
            print("❌ El lead no tiene row_id para actualizar en Sheets")
            return

        updated = sheets.update_send_status(
            row_id=int(target_lead.id),
            status=SendStatus.SENT,
            subject=email.subject,
        )
        if updated:
            print("✅ Estado actualizado en Sheets")
        else:
            print("⚠️  Email enviado, pero no se pudo actualizar el estado en Sheets")
        
        # PASO 7: Mostrar resumen
        print("\n" + "=" * 70)
        print("📊 RESUMEN DEL ENVÍO:")
        print("=" * 70)
        print(f"✅ Destinatario: {target_lead.contact_name}")
        print(f"✅ Email: {target_lead.email}")
        print(f"✅ Empresa: {target_lead.business_name}")
        print(f"✅ Asunto: {email.subject}")
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
