"""
Gmail Service - Integración con Gmail API para envío de mails.
Usa OAuth2 con flujo de escritorio.
"""
import logging
import os
import base64
import html
from pathlib import Path
from typing import Optional, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from core.models import Email
from core.constants import EMAIL_SIGNATURE

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.settings.basic",
]


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
        AUTOMÁTICAMENTE agrega la firma del usuario.
        
        Args:
            email: Objeto Email con to, subject, body
        
        Returns:
            message_id si tuvo éxito, None si falló
        """
        try:
            # IMPORTANTE: Agregar firma automáticamente
            # Igual que cuando redactas un email en Gmail manualmente
            #
            # Si email.html_body viene seteado (ej. para tener un link real
            # con texto tipo "portfolio" en vez del URL pelado), se manda
            # ese como HTML sin escapar - email.body sigue siendo el
            # fallback de texto plano que exige el modelo.
            if email.html_body:
                body_with_signature, subtype = self._add_signature_to_body(email.html_body, ya_es_html=True)
            else:
                body_with_signature, subtype = self._add_signature_to_body(email.body)
            
            # Construye mensaje MIME
            message = MIMEText(body_with_signature, subtype)
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
            logger.info(f"   Incluida: Firma automática del usuario")
            return message_id
        
        except HttpError as e:
            logger.error(f"❌ Error enviando mail a {email.to}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error inesperado: {e}")
            return None

    def send_email_con_adjunto(self, to: str, subject: str, body: str, adjunto_path: str) -> Optional[str]:
        """Igual que send_email pero con un archivo adjunto (ej. el PDF del
        presupuesto) - usa MIMEMultipart en vez de MIMEText simple."""
        try:
            body_with_signature, subtype = self._add_signature_to_body(body)

            message = MIMEMultipart()
            message["To"] = to
            message["Subject"] = subject
            message.attach(MIMEText(body_with_signature, subtype))

            ruta = Path(adjunto_path)
            with open(ruta, "rb") as f:
                parte = MIMEApplication(f.read(), _subtype=ruta.suffix.lstrip(".") or "octet-stream")
            parte.add_header("Content-Disposition", "attachment", filename=ruta.name)
            message.attach(parte)

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            result = self.service.users().messages().send(
                userId="me",
                body={"raw": raw_message}
            ).execute()

            message_id = result.get("id")
            logger.info(f"✅ Mail con adjunto enviado a {to} (ID: {message_id})")
            return message_id

        except HttpError as e:
            logger.error(f"❌ Error enviando mail con adjunto a {to}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error inesperado enviando adjunto: {e}")
            return None

    def estado_bandeja_entrada(self, dias: int = 30, max_hilos: int = 80) -> list[dict]:
        """Recorre los hilos con actividad reciente en la bandeja de entrada
        (usa gmail.readonly, ya autorizado - no manda ni modifica nada) y
        para cada uno indica si el ULTIMO mensaje es nuestro (ya respondimos,
        tiene label SENT) o del remitente (falta responder).

        Una sola query de listado + un get por hilo unico - pensado para un
        volumen chico/mediano (decenas de hilos), no miles.
        """
        import re as _re

        try:
            resultados = []
            hilos_vistos = set()
            query = f"in:inbox newer_than:{dias}d"
            page_token = None

            while len(hilos_vistos) < max_hilos:
                resp = self.service.users().messages().list(
                    userId="me", q=query, pageToken=page_token, maxResults=50
                ).execute()
                mensajes = resp.get("messages", [])
                if not mensajes:
                    break

                for m in mensajes:
                    thread_id = m["threadId"]
                    if thread_id in hilos_vistos:
                        continue
                    hilos_vistos.add(thread_id)

                    hilo = self.service.users().threads().get(
                        userId="me", id=thread_id, format="metadata",
                        metadataHeaders=["From", "Subject", "Date"],
                    ).execute()
                    msgs_hilo = hilo.get("messages", [])
                    if not msgs_hilo:
                        continue
                    ultimo = msgs_hilo[-1]
                    headers = {h["name"]: h["value"] for h in ultimo["payload"].get("headers", [])}
                    de = headers.get("From", "")
                    match = _re.search(r"[\w\.\-]+@[\w\.\-]+", de)
                    remitente = match.group(0).lower() if match else de

                    resultados.append({
                        "thread_id": thread_id,
                        "remitente": remitente,
                        "asunto": headers.get("Subject", ""),
                        "fecha": headers.get("Date", ""),
                        "falta_responder": "SENT" not in ultimo.get("labelIds", []),
                        "cantidad_mensajes": len(msgs_hilo),
                    })
                    if len(hilos_vistos) >= max_hilos:
                        break

                page_token = resp.get("nextPageToken")
                if not page_token:
                    break

            return resultados
        except Exception as e:
            logger.error(f"❌ Error leyendo bandeja de entrada: {e}")
            return []

    def get_user_email(self) -> Optional[str]:
        """Obtiene el email del usuario autenticado."""
        try:
            profile = self.service.users().getProfile(userId="me").execute()
            return profile.get("emailAddress")
        except Exception as e:
            logger.error(f"❌ Error obteniendo perfil: {e}")
            return None
    
    def get_user_signature(self) -> Optional[str]:
        """
        Obtiene la firma del usuario desde Gmail Settings.
        Si no tiene firma configurada, retorna None.
        """
        try:
            # Lista aliases de envío y prioriza la cuenta principal
            response = self.service.users().settings().sendAs().list(userId="me").execute()
            send_as_items = response.get("sendAs", [])
            
            # Firma de cuenta principal primero
            send_as_items.sort(key=lambda item: not item.get("isPrimary", False))
            
            for item in send_as_items:
                signature = item.get("signature")
                if signature:
                    logger.info("✅ Firma de Gmail obtenida desde configuración")
                    return signature
            
            logger.debug("ℹ️  Usuario no tiene firma configurada en Gmail")
            return None
        
        except Exception as e:
            logger.debug(f"ℹ️  No se pudo obtener firma de Gmail: {e}")
            return None
    
    def _add_signature_to_body(self, body: str, ya_es_html: bool = False) -> Tuple[str, str]:
        """
        Agrega la firma al body del email.
        Intenta obtener la firma de Gmail, si no existe usa la firma por defecto.

        Args:
            ya_es_html: True si `body` ya viene armado como HTML (ej. con
                un <a href> real, como el link a "portfolio") - en ese caso
                NO se escapa, se manda tal cual.

        Returns:
            Tuple (body_con_firma, tipo_mime)
        """
        if ya_es_html:
            gmail_signature = self.get_user_signature()
            firma_html = gmail_signature or html.escape(EMAIL_SIGNATURE).replace("\n", "<br>")
            return f"{body}<br><br>{firma_html}", "html"

        # Intenta obtener firma de Gmail
        gmail_signature = self.get_user_signature()
        if gmail_signature:
            # La firma de Gmail suele ser HTML (incluye imagen/logo y links).
            # Convertimos el cuerpo de texto a HTML para que renderice correctamente.
            body_html = html.escape(body).replace("\n", "<br>")
            return f"{body_html}<br><br>{gmail_signature}", "html"

        # Si no hay firma en Gmail, usa la firma por defecto
        return f"{body}\n\n{EMAIL_SIGNATURE}", "plain"