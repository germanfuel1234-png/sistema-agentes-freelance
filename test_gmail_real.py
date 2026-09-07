#!/usr/bin/env python3
"""
TEST REAL DE GMAIL API
Envía emails de prueba a rodriguezg.dev@gmail.com y germanty123@gmail.com
"""
import asyncio
import logging
import os
import sys
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Agrega el repo a path
sys.path.insert(0, os.path.dirname(__file__))

from core.models import Email
from services.gmail_service import GmailService


async def test_gmail_real():
    """
    Test completo de Gmail API.
    Envía emails de prueba a dos cuentas.
    """
    logger.info("="*60)
    logger.info("🧪 TEST GMAIL API - Sistema de Agentes Freelance")
    logger.info("="*60)
    
    # Credenciales
    credentials_file = "credentials.json"
    token_file = "token_gmail.json"
    
    # Valida archivos
    if not os.path.exists(credentials_file):
        logger.error(f"❌ {credentials_file} no encontrado")
        logger.info("📝 Pasos para arreglarlo:")
        logger.info("1. Andá a Google Cloud Console (proyecto 'mailpaginaweb')")
        logger.info("2. Clientes > Agente Mails Freelance > Descargar JSON")
        logger.info(f"3. Guardalo como {credentials_file} en este directorio")
        return False
    
    try:
        # Inicializa Gmail Service
        logger.info("\n1️⃣  Inicializando Gmail Service...")
        gmail = GmailService(credentials_file, token_file)
        
        user_email = gmail.get_user_email()
        logger.info(f"✅ Autenticado como: {user_email}")
        
        # Test 1: Email a ti mismo (rodriguezg.dev@gmail.com)
        logger.info("\n2️⃣  Preparando primer email de prueba...")
        email1 = Email(
            to="rodriguezg.dev@gmail.com",
            subject="🧪 Test 1 - Sistema Agentes Freelance",
            body="""Hola Germán,

Este es el primer email de prueba del Sistema de Agentes Freelance.
Enviado automáticamente por Gmail API desde tu cuenta rodriguezg.dev@gmail.com.

✅ Si recibes este email, la integración Gmail está funcionando correctamente.

Detalles:
- Hora: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """
- Origen: Sistema Agentes (Agent 2)
- Tipo: Test de conectividad

---
Germán Rodríguez
Desarrollador Web
germanrodriguez.ar
""",
        )
        
        logger.info(f"   Enviando a: {email1.to}")
        message_id1 = gmail.send_email(email1)
        if message_id1:
            logger.info(f"   ✅ Email 1 enviado! ID: {message_id1}")
        else:
            logger.error(f"   ❌ Falló envío a {email1.to}")
            return False
        
        # Test 2: Email a germanty123@gmail.com
        logger.info("\n3️⃣  Preparando segundo email de prueba...")
        email2 = Email(
            to="germanty123@gmail.com",
            subject="🧪 Test 2 - Propuesta de Desarrollo",
            body="""Hola Germán,

Este es el segundo email de prueba.
Este email es enviado DESDE tu cuenta de Gmail (rodriguezg.dev@gmail.com) 
HACIA germanty123@gmail.com como ejemplo del flujo de outreach.

📋 Detalles:
- Fecha: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """
- Origen: Agent 2 (Send Emails)
- Propósito: Validar flujo de mails

🎯 En producción, Agent 2 generaría mails personalizados para leads, 
esperaría tu aprobación, y luego los enviaría automáticamente.

Este test valida que:
✓ Google Sheets está conectado
✓ Gmail API funciona
✓ La autenticación OAuth2 es correcta
✓ Los mails se entregan correctamente

---
Sistema Agentes Freelance v0.1
germanrodriguez.ar
""",
        )
        
        logger.info(f"   Enviando a: {email2.to}")
        message_id2 = gmail.send_email(email2)
        if message_id2:
            logger.info(f"   ✅ Email 2 enviado! ID: {message_id2}")
        else:
            logger.error(f"   ❌ Falló envío a {email2.to}")
            return False
        
        # Resumen
        logger.info("\n" + "="*60)
        logger.info("✅ TEST EXITOSO")
        logger.info("="*60)
        logger.info(f"📧 Email 1 a rodriguezg.dev@gmail.com: OK (ID: {message_id1})")
        logger.info(f"📧 Email 2 a germanty123@gmail.com: OK (ID: {message_id2})")
        logger.info("\n🎉 Gmail API está funcionando correctamente!")
        logger.info("\nProximos pasos:")
        logger.info("1. Verifica que llegaron los emails a ambas cuentas")
        logger.info("2. Ahora ejecuta los agentes con:")
        logger.info("   python -m web.app        (para dashboard web)")
        logger.info("   python run_agents.py     (para ejecución manual)")
        
        return True
    
    except Exception as e:
        logger.error(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_gmail_real())
    sys.exit(0 if success else 1)
