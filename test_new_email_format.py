"""
Test del nuevo formato de email simplificado
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from services.gemini_service import GeminiService
from services.gmail_service import GmailService

def test_new_email_format():
    """Verifica el nuevo formato de email"""
    
    print("=" * 70)
    print("🧪 TEST: Nuevo formato de email simplificado")
    print("=" * 70)
    
    gemini = GeminiService()
    gmail = GmailService('credentials.json', 'token_gmail.json')
    
    # Generar email
    print("\n1️⃣  Generando email para test...")
    email_body = gemini.generate_email_for_lead(
        lead_name="Juan García López",
        business_name="Marketing Pro SRL",  # No se usa en nuevo formato
        industry="Marketing",  # No se usa en nuevo formato
        specific_note="",  # No se usa en nuevo formato
        template="marketing"
    )
    
    print("\n📧 EMAIL GENERADO (sin firma):")
    print("-" * 70)
    print(email_body)
    print("-" * 70)
    
    # Verificar elementos clave
    print("\n2️⃣  VERIFICANDO ELEMENTOS CLAVE:")
    print("-" * 70)
    
    checks = {
        "Saludo personalizado": "Hola Juan García López" in email_body,
        "Identidad del remitente": "Soy Germán Rodríguez" in email_body,
        "Descripción de servicios": "webs, landings y sistemas" in email_body or "webs" in email_body.lower(),
        "URL del portafolio": "germanrodriguez.ar" in email_body,
        "Propuesta de valor": "desarrollador web freelance" in email_body.lower() or "developer" in email_body.lower(),
        "Despedida": "Saludos," in email_body,
        "Nombre del firma": "Germán Rodríguez" in email_body,
    }
    
    for check, result in checks.items():
        status = "✅" if result else "❌"
        print(f"{status} {check}: {result}")
    
    # Agregar firma automática
    print("\n3️⃣  AGREGANDO FIRMA AUTOMÁTICA:")
    print("-" * 70)
    
    email_with_signature = gmail._add_signature_to_body(email_body)
    print("\n📧 EMAIL FINAL (con firma automática):")
    print("-" * 70)
    print(email_with_signature)
    print("-" * 70)
    
    # Verificar firma
    print("\n4️⃣  VERIFICANDO FIRMA:")
    print("-" * 70)
    
    has_signature = "DESARROLLO WEB" in email_with_signature
    has_contact = "rodriguezg.dev@gmail.com" in email_with_signature
    has_web = "germanrodriguez.ar" in email_with_signature
    
    print(f"✅ Incluida firma profesional: {has_signature}")
    print(f"✅ Incluido email: {has_contact}")
    print(f"✅ Incluida web: {has_web}")
    
    # Resumen
    print("\n5️⃣  RESUMEN:")
    print("-" * 70)
    
    all_checks_pass = all(checks.values())
    signature_ok = has_signature and has_contact
    
    if all_checks_pass and signature_ok:
        print("✅ ¡TODO CORRECTO!")
        print("\n📌 EL EMAIL:")
        print("   • Es simple y directo")
        print("   • Personaliza solo con el nombre del cliente")
        print("   • Incluye propuesta de valor clara")
        print("   • Tiene firma automática profesional")
        print("   • Está listo para enviar")
        return True
    else:
        print("❌ FALLÓ ALGUNA VERIFICACIÓN")
        return False

if __name__ == "__main__":
    success = test_new_email_format()
    print("\n" + "=" * 70)
    sys.exit(0 if success else 1)
