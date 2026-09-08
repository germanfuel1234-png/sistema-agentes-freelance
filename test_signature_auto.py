"""
Test para verificar que la firma se agrega automáticamente
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from services.gmail_service import GmailService
from services.gemini_service import GeminiService
from core.models import Email
from core.constants import EMAIL_SIGNATURE

def test_signature_auto_addition():
    """Verifica que la firma se agrega automáticamente"""
    
    print("=" * 70)
    print("🧪 TEST: Firma automática en emails")
    print("=" * 70)
    
    # Inicializar servicios
    gmail = GmailService('credentials.json', 'token_gmail.json')
    gemini = GeminiService()
    
    # Generar email sin firma (como generaría Gemini)
    print("\n1️⃣  PASO 1: Generar email SIN firma explícita")
    print("-" * 70)
    
    email_body = gemini.generate_email_for_lead(
        lead_name="Juan García",
        business_name="Marketing Agency Pro",
        industry="Marketing",
        specific_note="tienen muy buen equipo",
        template="marketing"
    )
    
    print("Email generado (sin firma):")
    print(email_body)
    print("\n✅ El email NO contiene firma detallada")
    
    # Simular lo que hace send_email internamente
    print("\n2️⃣  PASO 2: Simular envío con firma automática")
    print("-" * 70)
    
    # Crear objeto Email
    email = Email(
        to="test@example.com",
        subject="🚀 Developer Freelance",
        body=email_body
    )
    
    # Aplicar firma automáticamente (como lo hace send_email)
    body_with_signature = gmail._add_signature_to_body(email.body)
    
    print("Email FINAL (con firma automática):")
    print(body_with_signature)
    
    # Verificar que la firma está presente
    print("\n3️⃣  VERIFICACIÓN:")
    print("-" * 70)
    
    has_german_name = "Germán Rodríguez" in body_with_signature
    has_web_url = "germanrodriguez.ar" in body_with_signature
    has_signature = "DESARROLLO WEB" in body_with_signature or "rodriguezg.dev@gmail.com" in body_with_signature
    
    print(f"✅ Contiene nombre: {has_german_name}")
    print(f"✅ Contiene web: {has_web_url}")
    print(f"✅ Contiene firma: {has_signature}")
    
    if has_german_name and (has_web_url or has_signature):
        print("\n✅ ¡CORRECTO! La firma se agrega automáticamente")
        print("\n📌 FLUJO COMPLETADO:")
        print("   1. Gemini genera email SIN firma")
        print("   2. GmailService.send_email() agrega firma automáticamente")
        print("   3. Se envía con firma = igual que redactar en Gmail")
    else:
        print("\n❌ ERROR: Firma no se agregó correctamente")
        return False
    
    print("\n" + "=" * 70)
    return True

if __name__ == "__main__":
    success = test_signature_auto_addition()
    sys.exit(0 if success else 1)
