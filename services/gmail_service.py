"""
Gmail Service - Integración con Gmail API para envío de mails.
Usa OAuth2 con flujo de escritorio.
"""
import logging
import os
import base64
from pathlib import Path
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from core.models import Email

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class GmailService:
    """
    Servicio para enviar mails vía Gmail API.
    Maneja OAuth2 automáticamente.
    """
    
    def __init__(self, 
                 credentials_file: str = "credentials.json",
                 token_file: str = "token_gmail.json"):
        """
        Args:
            credentials_file: Path a credentials.json descargado de Google Cloud
            token_file: Path donde guardar/cargar el token persistente
        """
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None
        self.creds = None
        self._authenticate()
    
    def _authenticate(self):
        """Autentica con Gmail API usando OAuth2."""
        try:
            # Intenta cargar token existente
            if Path(self.token_file).exists():
                self.creds = Credentials.from_authorized_user_file(
                    self.token_file, SCOPES
                )
            
            # Si no hay token o está expirado, solicita nuevo
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    try:
                        self.creds.refresh(Request())
                    except RefreshError:
                        logger.warning("Token expirado, requiere nuevo login")
                        self._new_flow()
                else:
                    self._new_flow()
                
                # Guarda token para futuras ejecuciones
                with open(self.token_file, "w") as token:
                    token.write(self.creds.to_json())
            
            self.service = build("gmail", "v1", credentials=self.creds)
            logger.info("✅ Autenticado con Gmail API")
        
        except FileNotFoundError:
            logger.error(f"❌ Archivo de credenciales no encontrado: {self.credentials_file}")
            logger.info("ℹ️  Descargá credentials.json desde Google Cloud Console")
            raise
        except Exception as e:
            logger.error(f"❌ Error en autenticación Gmail: {e}")
            raise
    
    def _new_flow(self):
        """Inicia flujo OAuth2 nuevo."""
        if not Path(self.credentials_file).exists():
            raise FileNotFoundError(
                f"{self.credentials_file} no encontrado. "
                "Descárgalo de Google Cloud Console."
            )
        
        flow = InstalledAppFlow.from_client_secrets_file(
            self.credentials_file, SCOPES
        )
        self.creds = flow.run_local_server(port=0)
    
    def send_email(self, email: Email) -> Optional[str]:
        """
        Envía un email.
        
        Args:
            email: Objeto Email con to, subject, body
        
        Returns:
            message_id si tuvo éxito, None si falló
        """
        try:
            # Construye mensaje MIME
            message = MIMEText(email.body, "html" if email.html_body else "plain")
            message["To"] = email.to
            message["Subject"] = email.subject
            
            if email.cc:
                message["Cc"] = ", ".join(email.cc)
            
            # Codifica en base64
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            # Envía
            result = self.service.users().messages().send(
                userId="me",
                body={"raw": raw_message}
            ).execute()
            
            message_id = result.get("id")
            logger.info(f"✅ Mail enviado a {email.to} (ID: {message_id})")
            return message_id
        
        except HttpError as e:
            logger.error(f"❌ Error enviando mail a {email.to}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error inesperado: {e}")
            return None
    
    def get_user_email(self) -> Optional[str]:
        """Obtiene el email del usuario autenticado."""
        try:
            profile = self.service.users().getProfile(userId="me").execute()
            return profile.get("emailAddress")
        except Exception as e:
            logger.error(f"❌ Error obteniendo perfil: {e}")
            return None
