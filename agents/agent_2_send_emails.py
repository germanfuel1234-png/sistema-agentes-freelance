"""
Agent 2 - Redactor y Enviador de Mails (Actualizado)
Toma leads Pendiente, arma borrador con Gemini, espera aprobación, luego envía con Gmail real.
"""
import logging
from datetime import datetime
from typing import Any, List

from agents.base_agent import BaseAgent
from core.models import Lead, Email, SendStatus
from core.sheets_client import SheetsClient
from core.constants import EMAIL_TEMPLATE_SUBJECT, EMAIL_TEMPLATE_BODY
from services.gmail_service import GmailService
from services.gemini_service import GeminiService

logger = logging.getLogger(__name__)


class Agent2SendEmails(BaseAgent):
    """
    Redacta mails a leads pendientes con Gemini, 
    espera tu aprobación, y luego envía con Gmail real.
    """
    
    def __init__(self, sheets_client: SheetsClient, 
                 gmail_service: GmailService = None,
                 gemini_service: GeminiService = None):
        super().__init__("agent_2_send_emails")
        self.sheets = sheets_client
        self.gmail = gmail_service
        self.gemini = gemini_service
        self.emails_to_send: List[Email] = []
    
    async def execute(self, 
                     limit: int = 5,
                     **kwargs) -> tuple[Any, bool]:
        """
        Prepara mails para leads pendientes.
        
        Returns:
            (Lista de mails listos para revisar, True) - REQUIERE APROBACIÓN
        """
        logger.info(f"✉️  {self.name}: preparando mails pendientes...")
        
        try:
            pending_leads = self.sheets.get_pending_leads()[:limit]
            
            if not pending_leads:
                logger.info("ℹ️  No hay leads pendientes")
                return {"emails": [], "count": 0}, False
            
            emails = []
            for lead in pending_leads:
                # Usa Gemini si está disponible, si no usa template
                if self.gemini:
                    body = self.gemini.generate_email_for_lead(
                        lead_name=lead.contact_name or "amigo",
                        business_name=lead.business_name,
                        industry=lead.industry or "general",
                        template="marketing" if "Marketing" in lead.track.value else "pymes"
                    )
                else:
                    body = EMAIL_TEMPLATE_BODY.format(
                        contact_name=lead.contact_name or "amigo"
                    )
                
                email = Email(
                    to=lead.email,
                    subject=EMAIL_TEMPLATE_SUBJECT,
                    body=body,
                    lead_id=lead.id,
                )
                emails.append(email)
            
            self.emails_to_send = emails
            logger.info(f"📋 {len(emails)} mails preparados, esperando tu aprobación")
            
            # RETORNA RESULTADO PARA REVIEW
            return {
                "emails": emails,
                "count": len(emails),
                "preview": [
                    {
                        "to": e.to,
                        "subject": e.subject,
                        "body_preview": e.body[:150] + "..."
                    }
                    for e in emails
                ]
            }, True  # ✓ REQUIERE APROBACIÓN
        
        except Exception as e:
            logger.error(f"❌ Error en Agent 2: {e}")
            raise
    
    async def on_approved(self, output: Any) -> None:
        """
        Usuario aprobó. Ahora sí enviamos los mails con Gmail real.
        """
        logger.info(f"✅ Aprobación recibida. Enviando {len(self.emails_to_send)} mails...")
        
        if not self.gmail:
            logger.warning("⚠️  Gmail no configurado, modo simulado")
            for email in self.emails_to_send:
                logger.info(f"📧 [MOCK] Mail a {email.to}: {email.subject}")
            return
        
        sent_count = 0
        for email in self.emails_to_send:
            try:
                message_id = self.gmail.send_email(email)
                
                if message_id:
                    # Actualiza Sheet
                    leads = self.sheets.get_all_leads()
                    for l in leads:
                        if l.id == email.lead_id:
                            l.send_status = SendStatus.SENT
                            l.send_date = datetime.now()
                            l.subject_used = email.subject
                            self.sheets.update_lead(l, int(l.id))
                            sent_count += 1
                            break
                    
                    logger.info(f"📬 Mail enviado a {email.to}")
            
            except Exception as e:
                logger.error(f"❌ Error enviando a {email.to}: {e}")
        
        logger.info(f"✅ {sent_count}/{len(self.emails_to_send)} mails enviados")
