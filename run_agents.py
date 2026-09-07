#!/usr/bin/env python3
"""
Script maestro: Ejecuta todos los agentes en secuencia.
Flujo completo: Agent 0 → Agent 1 → Agent 4 → Agent 2 → Agent 3
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

# Agrega repo a path
sys.path.insert(0, os.path.dirname(__file__))

from core.sheets_client import SheetsClient
from core.models import Email
from agents.agent_0_web_study import Agent0WebStudy
from agents.agent_1_search_leads import Agent1SearchLeads
from agents.agent_2_send_emails import Agent2SendEmails
from agents.agent_3_budgets import Agent3BudgetBuilder
from agents.agent_4_supervisor import Agent4Supervisor
from services.gmail_service import GmailService
from services.gemini_service import GeminiService


async def main():
    """
    Orquesta la ejecución completa de agentes.
    """
    logger.info("="*70)
    logger.info("🤖 SISTEMA AGENTES FREELANCE - EJECUCIÓN COMPLETA")
    logger.info("="*70)
    logger.info(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Inicializa servicios
    try:
        sheets = SheetsClient()
        logger.info("✅ Google Sheets conectado")
    except Exception as e:
        logger.error(f"❌ Error con Sheets: {e}")
        return False
    
    # Gmail (opcional)
    gmail = None
    if os.path.exists("credentials.json"):
        try:
            gmail = GmailService("credentials.json", "token_gmail.json")
            logger.info("✅ Gmail API conectado")
        except Exception as e:
            logger.warning(f"⚠️  Gmail no disponible: {e}")
    
    # Gemini (opcional)
    gemini = GeminiService()  # Modo template por defecto
    if os.getenv("GEMINI_API_KEY"):
        logger.info("✅ Gemini API disponible")
    else:
        logger.info("ℹ️  Gemini en modo template")
    
    # Inicializa agentes
    agent_0 = Agent0WebStudy(sheets)
    agent_1 = Agent1SearchLeads(sheets)
    agent_2 = Agent2SendEmails(sheets, gmail, gemini)
    agent_3 = Agent3BudgetBuilder(sheets, gemini)
    agent_4 = Agent4Supervisor(sheets, gmail)
    
    try:
        # PASO 1: Agent 4 - Verificación inicial
        logger.info("\n" + "="*70)
        logger.info("📊 PASO 1/5: Agent 4 (Supervisor) - Validar sistema")
        logger.info("="*70)
        
        supervisor_report, _ = await agent_4.execute()
        logger.info(f"Status: {supervisor_report.get('status', 'UNKNOWN')}")
        for check, details in supervisor_report.get('checks', {}).items():
            logger.info(f"  - {check}: {details.get('status', 'N/A')}")
        
        # PASO 2: Agent 0 - Estudio web
        logger.info("\n" + "="*70)
        logger.info("🌐 PASO 2/5: Agent 0 (Web Study) - Analizar germanrodriguez.ar")
        logger.info("="*70)
        
        web_study, _ = await agent_0.execute()
        logger.info(f"✅ Servicios encontrados: {len(web_study.services)}")
        for service in web_study.services[:3]:  # Muestra primeros 3
            logger.info(f"   - {service.service}: ${service.base_price_ars:,.0f} ARS")
        
        # PASO 3: Agent 1 - Búsqueda de leads
        logger.info("\n" + "="*70)
        logger.info("🔍 PASO 3/5: Agent 1 (Search Leads) - Buscar nuevas PyMEs")
        logger.info("="*70)
        
        new_leads, _ = await agent_1.execute(
            search_type="pymes",
            industry="tecnología",
            city="Argentina",
            limit=5
        )
        logger.info(f"✅ Leads encontrados: {len(new_leads)}")
        for lead in new_leads[:3]:  # Muestra primeros 3
            logger.info(f"   - {lead.business_name} ({lead.contact_email})")
        
        # PASO 4: Agent 2 - Envío de emails (CON APROBACIÓN)
        logger.info("\n" + "="*70)
        logger.info("📧 PASO 4/5: Agent 2 (Send Emails) - Generar emails")
        logger.info("="*70)
        
        emails_draft, requires_approval = await agent_2.execute(limit=3)
        
        if requires_approval:
            logger.info(f"⏸️  REQUIERE APROBACIÓN DE USUARIO")
            logger.info(f"\n📬 Preview de emails a enviar ({len(emails_draft)} total):\n")
            
            for i, email in enumerate(emails_draft, 1):
                logger.info(f"   [{i}] Para: {email.to}")
                logger.info(f"       Asunto: {email.subject}")
                logger.info(f"       Body (primeras 150 chars): {email.body[:150]}...\n")
            
            # Pregunta aprobación
            response = input("¿Aprobar envío de estos emails? (s/n): ").strip().lower()
            
            if response == 's':
                logger.info("\n✅ Aprobado! Enviando emails...")
                await agent_2.on_approved(emails_draft)
                logger.info("✅ Emails enviados exitosamente")
            else:
                logger.info("\n❌ Envío cancelado por usuario")
        
        # PASO 5: Agent 3 - Armador de presupuesto (EJEMPLO)
        logger.info("\n" + "="*70)
        logger.info("💰 PASO 5/5: Agent 3 (Budget Builder) - Ejemplo presupuesto")
        logger.info("="*70)
        
        # Ejemplo: un cliente quiere una landing page con CRM
        budget, requires_approval = await agent_3.execute(
            client_name="Ejemplo Cliente SRL",
            project_description="Landing page de servicios con integración CRM y pagos online"
        )
        
        logger.info(f"\n💵 Presupuesto generado para: {budget.client_name}")
        logger.info(f"   Base: ${budget.base_price_ars:,.0f} ARS")
        logger.info(f"   Ajustes: +${budget.adjustments_ars:,.0f} ARS")
        logger.info(f"   Total: ${budget.total_price_ars:,.0f} ARS")
        logger.info(f"   Plazo: {budget.estimated_days} días")
        
        if requires_approval:
            response = input("\n¿Aprobar este presupuesto? (s/n): ").strip().lower()
            
            if response == 's':
                logger.info("✅ Presupuesto aprobado!")
                await agent_3.on_approved(budget)
                logger.info("✅ Presupuesto guardado en Sheet")
            else:
                logger.info("❌ Presupuesto rechazado")
        
        # RESUMEN FINAL
        logger.info("\n" + "="*70)
        logger.info("✅ EJECUCIÓN COMPLETADA")
        logger.info("="*70)
        logger.info(f"Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("\n🎯 Próximos pasos:")
        logger.info("   1. Revisar leads en Google Sheets (tab: leads_tracking)")
        logger.info("   2. Verificar emails en el inbox (rodriguezg.dev@gmail.com)")
        logger.info("   3. Monitorear respuestas y follow-ups")
        logger.info("\n📊 Dashboard web: python -m uvicorn web.app:app --reload")
        
        return True
    
    except Exception as e:
        logger.error(f"\n❌ ERROR FATAL: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
