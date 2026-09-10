"""
Cliente para interactuar con Google Sheets.
Maneja lectura/escritura de leads, presupuestos, precios.
"""
import logging
import re
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config.settings import settings
from core.models import Lead, Budget, Price, SendStatus, TrackType, BudgetStatus

logger = logging.getLogger(__name__)

# Scopes para Google Sheets API
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsClient:
    """Cliente para Google Sheets con métodos CRUD para leads, presupuestos, etc."""
    
    def __init__(self, credentials_file: str = "credentials.json", token_file: str = "token.json"):
        """
        Inicializa el cliente con OAuth2.
        
        Args:
            credentials_file: Archivo credentials.json descargado de Google Cloud
            token_file: Archivo de token persistente (se crea automáticamente)
        """
        self.sheet_id = settings.google_sheet_id
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None
        self.creds = None
        self._sheet_titles_cache: Optional[List[str]] = None
        self._authenticate()

    @staticmethod
    def _quote_sheet_name(sheet_name: str) -> str:
        """Escapa y envuelve el nombre de pestaña para rangos A1."""
        escaped = sheet_name.replace("'", "''")
        return f"'{escaped}'"

    @staticmethod
    def _extract_sheet_and_a1(range_name: str) -> tuple[Optional[str], Optional[str]]:
        """Separa un rango A1 (ej. Sheet!A1:Z100) en (sheet, a1)."""
        if "!" not in range_name:
            return None, None
        sheet_name, a1_range = range_name.split("!", 1)
        clean_sheet = sheet_name.strip().strip("'").strip('"')
        return clean_sheet, a1_range

    @staticmethod
    def _column_index_to_letter(index: int) -> str:
        """Convierte índice de columna base 0 a letra(s) A1 (0->A, 27->AB)."""
        result = ""
        n = index + 1
        while n > 0:
            n, rem = divmod(n - 1, 26)
            result = chr(65 + rem) + result
        return result

    @staticmethod
    def _normalize_sheet_name(name: str) -> str:
        """Normaliza para comparar nombres con/ sin espacios, guiones o mayúsculas."""
        return re.sub(r"[^a-z0-9]", "", name.lower())

    @staticmethod
    def _normalize_header(name: str) -> str:
        """Normaliza encabezados para matching tolerante."""
        return re.sub(r"[^a-z0-9]", "", (name or "").lower())

    def _find_header_index(self, headers: List[str], candidates: List[str]) -> Optional[int]:
        """Busca la columna por lista de posibles nombres de encabezado."""
        normalized_headers = [self._normalize_header(h) for h in headers]
        normalized_candidates = [self._normalize_header(c) for c in candidates]

        for candidate in normalized_candidates:
            if candidate in normalized_headers:
                return normalized_headers.index(candidate)
        return None

    @staticmethod
    def _safe_get(row: List[str], index: Optional[int]) -> str:
        """Retorna valor de celda por índice o string vacío."""
        if index is None:
            return ""
        if index < 0 or index >= len(row):
            return ""
        return str(row[index]).strip()

    @staticmethod
    def _extract_email(value: str) -> str:
        """Extrae el primer email válido desde un campo mixto (mail/IG/formulario)."""
        if not value:
            return ""
        match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", value)
        return match.group(0).strip() if match else ""

    @staticmethod
    def _parse_track(raw_track: str):
        """Mapea track textual a enum conocido."""
        normalized = (raw_track or "").strip().lower()
        if "pyme" in normalized:
            return TrackType.PYME
        return TrackType.MARKETING

    def _get_sheet_titles(self) -> List[str]:
        """Obtiene y cachea los nombres de pestañas del spreadsheet."""
        if self._sheet_titles_cache is not None:
            return self._sheet_titles_cache

        spreadsheet = self.service.spreadsheets().get(
            spreadsheetId=self.sheet_id,
            fields="sheets.properties.title"
        ).execute()
        titles = [
            s.get("properties", {}).get("title", "")
            for s in spreadsheet.get("sheets", [])
            if s.get("properties", {}).get("title")
        ]
        self._sheet_titles_cache = titles
        return titles

    def add_sheet(self, tab_name: str, headers: Optional[List[str]] = None) -> bool:
        """Crea una pestaña nueva si todavía no existe, con encabezados
        opcionales en la fila 1. Si ya existe, no hace nada (no la borra ni
        la pisa)."""
        if tab_name in self._get_sheet_titles():
            return False

        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]},
        ).execute()
        self._sheet_titles_cache = None  # invalida cache, la pestaña nueva ya existe

        if headers:
            self.write_range(f"{self._quote_sheet_name(tab_name)}!A1", [headers], append=False)
        return True

    def _resolve_range_with_existing_sheet(self, range_name: str) -> str:
        """
        Intenta resolver el nombre de pestaña del rango contra tabs existentes.
        Si no encuentra coincidencia, devuelve el rango original.
        """
        sheet_name, a1_range = self._extract_sheet_and_a1(range_name)
        if not sheet_name or not a1_range:
            return range_name

        titles = self._get_sheet_titles()
        if not titles:
            return range_name

        # 1) Match exacto
        if sheet_name in titles:
            return f"{self._quote_sheet_name(sheet_name)}!{a1_range}"

        normalized_target = self._normalize_sheet_name(sheet_name)

        # 2) Match normalizado (ej: leads_tracking vs Leads Tracking)
        for title in titles:
            if self._normalize_sheet_name(title) == normalized_target:
                logger.warning(
                    "⚠️  Rango '%s' no coincide exacto. Usando pestaña '%s'.",
                    sheet_name,
                    title,
                )
                return f"{self._quote_sheet_name(title)}!{a1_range}"

        # 3) Fallback para variantes con prefijo/sufijo
        for title in titles:
            normalized_title = self._normalize_sheet_name(title)
            if normalized_target in normalized_title or normalized_title in normalized_target:
                logger.warning(
                    "⚠️  Rango '%s' no existe. Fallback a pestaña '%s'.",
                    sheet_name,
                    title,
                )
                return f"{self._quote_sheet_name(title)}!{a1_range}"

        return range_name
    
    def _authenticate(self):
        """Autentica con Google Sheets API usando OAuth2."""
        try:
            # Intenta cargar token existente
            if Path(self.token_file).exists():
                self.creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
            
            # Si no hay token o está expirado, solicita nuevo
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES
                    )
                    self.creds = flow.run_local_server(port=0)
                
                # Guarda token para futuras ejecuciones
                with open(self.token_file, "w") as token:
                    token.write(self.creds.to_json())
            
            self.service = build("sheets", "v4", credentials=self.creds)
            logger.info("✅ Autenticado con Google Sheets API")
        
        except FileNotFoundError as e:
            logger.error(f"❌ Archivo de credenciales no encontrado: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error en autenticación: {e}")
            raise
    
    def read_range(self, range_name: str) -> List[List[str]]:
        """
        Lee un rango de la planilla.
        
        Args:
            range_name: Rango en formato "Sheet!A1:Z100"
        
        Returns:
            Lista de filas (cada fila es una lista de celdas)
        """
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=range_name
            ).execute()
            return result.get("values", [])
        except HttpError as e:
            error_text = str(e)
            if "Unable to parse range" in error_text and "!" in range_name:
                try:
                    resolved_range = self._resolve_range_with_existing_sheet(range_name)
                    if resolved_range != range_name:
                        logger.info(f"🔁 Reintentando lectura con rango resuelto: {resolved_range}")
                        result = self.service.spreadsheets().values().get(
                            spreadsheetId=self.sheet_id,
                            range=resolved_range
                        ).execute()
                        return result.get("values", [])
                except Exception as retry_error:
                    logger.error(f"❌ Error resolviendo rango {range_name}: {retry_error}")
            logger.error(f"❌ Error leyendo rango {range_name}: {e}")
            return []
    
    def write_range(self, range_name: str, values: List[List[str]], 
                   append: bool = False) -> bool:
        """
        Escribe/añade datos a un rango.
        
        Args:
            range_name: Rango en formato "Sheet!A1:Z100"
            values: Lista de filas para escribir
            append: Si True, añade al final. Si False, sobrescribe.
        
        Returns:
            True si tuvo éxito
        """
        try:
            body = {"values": values}
            if append:
                self.service.spreadsheets().values().append(
                    spreadsheetId=self.sheet_id,
                    range=range_name,
                    valueInputOption="RAW",
                    body=body
                ).execute()
            else:
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.sheet_id,
                    range=range_name,
                    valueInputOption="RAW",
                    body=body
                ).execute()
            logger.info(f"✅ Datos escritos en {range_name}")
            return True
        except HttpError as e:
            error_text = str(e)
            if "Unable to parse range" in error_text and "!" in range_name:
                try:
                    resolved_range = self._resolve_range_with_existing_sheet(range_name)
                    if resolved_range != range_name:
                        logger.info(f"🔁 Reintentando escritura con rango resuelto: {resolved_range}")
                        body = {"values": values}
                        if append:
                            self.service.spreadsheets().values().append(
                                spreadsheetId=self.sheet_id,
                                range=resolved_range,
                                valueInputOption="RAW",
                                body=body
                            ).execute()
                        else:
                            self.service.spreadsheets().values().update(
                                spreadsheetId=self.sheet_id,
                                range=resolved_range,
                                valueInputOption="RAW",
                                body=body
                            ).execute()
                        logger.info(f"✅ Datos escritos en {resolved_range}")
                        return True
                except Exception as retry_error:
                    logger.error(f"❌ Error resolviendo rango {range_name}: {retry_error}")
            logger.error(f"❌ Error escribiendo en {range_name}: {e}")
            return False
    
    # ========== LEADS ==========
    
    def get_all_leads(self) -> List[Lead]:
        """Obtiene todos los leads de leads_tracking."""
        rows = self.read_range(settings.google_sheet_leads_range)
        if not rows or len(rows) < 2:
            return []
        
        leads = []
        headers = rows[0]
        
        for i, row in enumerate(rows[1:], start=2):
            try:
                lead = self._row_to_lead(row, headers, row_id=i)
                if lead:
                    leads.append(lead)
            except Exception as e:
                logger.warning(f"⚠️  Error parseando fila {i}: {e}")
        
        return leads
    
    def get_pending_leads(self) -> List[Lead]:
        """Obtiene solo leads con Enviado?=Pendiente."""
        all_leads = self.get_all_leads()
        return [l for l in all_leads if l.is_pending()]
    
    def add_lead(self, lead: Lead) -> bool:
        """Añade un nuevo lead a la planilla."""
        row = lead.to_sheet_row()
        return self.write_range(
            settings.google_sheet_leads_range,
            [row],
            append=True
        )
    
    def update_lead(self, lead: Lead, row_id: int) -> bool:
        """Actualiza un lead existente (requiere row_id)."""
        row = lead.to_sheet_row()
        leads_range = settings.google_sheet_leads_range
        sheet_name, _ = self._extract_sheet_and_a1(leads_range)
        if not sheet_name:
            sheet_name = "leads_tracking"
        range_name = f"{sheet_name}!A{row_id}:L{row_id}"
        return self.write_range(range_name, [row], append=False)

    def update_send_status(self, row_id: int, status: SendStatus, subject: str = "") -> bool:
        """
        Actualiza solo columnas de envío (fecha/asunto/estado) para evitar romper esquemas distintos.
        """
        try:
            leads_range = settings.google_sheet_leads_range
            configured_sheet, _ = self._extract_sheet_and_a1(leads_range)
            if not configured_sheet:
                configured_sheet = "leads_tracking"

            # Resuelve nombre real del tab si difiere del configurado
            resolved = self._resolve_range_with_existing_sheet(f"{configured_sheet}!A1:A1")
            resolved_sheet, _ = self._extract_sheet_and_a1(resolved)
            if not resolved_sheet:
                resolved_sheet = configured_sheet

            header_range = f"{self._quote_sheet_name(resolved_sheet)}!1:1"
            header_rows = self.read_range(header_range)
            if not header_rows:
                logger.error("❌ No se pudieron leer encabezados de leads")
                return False

            headers = header_rows[0]
            idx_date = self._find_header_index(headers, ["Fecha envio", "Fecha envío", "send_date"])
            idx_subject = self._find_header_index(headers, ["Asunto usado", "subject_used", "asunto"])
            idx_status = self._find_header_index(headers, ["Enviado?", "send_status", "estado envio"])

            if idx_status is None:
                logger.error("❌ No se encontró columna de estado de envío en la hoja")
                return False

            date_value = datetime.now().strftime("%d/%m/%Y")
            status_value = "✅ Enviado" if status == SendStatus.SENT else "⬜ Pendiente"

            updates = []
            if idx_date is not None:
                updates.append({
                    "range": f"{self._quote_sheet_name(resolved_sheet)}!{self._column_index_to_letter(idx_date)}{row_id}",
                    "values": [[date_value]],
                })

            if idx_subject is not None and subject:
                updates.append({
                    "range": f"{self._quote_sheet_name(resolved_sheet)}!{self._column_index_to_letter(idx_subject)}{row_id}",
                    "values": [[subject]],
                })

            updates.append({
                "range": f"{self._quote_sheet_name(resolved_sheet)}!{self._column_index_to_letter(idx_status)}{row_id}",
                "values": [[status_value]],
            })

            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.sheet_id,
                body={
                    "valueInputOption": "RAW",
                    "data": updates,
                },
            ).execute()

            logger.info("✅ Estado de envío actualizado en fila %s", row_id)
            return True

        except HttpError as e:
            logger.error(f"❌ Error actualizando estado de envío en fila {row_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error inesperado actualizando estado de envío: {e}")
            return False
    
    def _row_to_lead(self, row: List[str], headers: List[str], row_id: int) -> Optional[Lead]:
        """Convierte una fila a objeto Lead."""
        if len(row) < 6:  # Mínimo campos esperados
            return None
        
        try:
            idx_business = self._find_header_index(headers, ["Negocio/Agencia", "business_name", "empresa", "negocio"])
            idx_contact = self._find_header_index(headers, ["Contacto", "contact_name", "nombre contacto"])
            idx_track = self._find_header_index(headers, ["Track (PyME/Marketing)", "track"])
            idx_industry = self._find_header_index(headers, ["Rubro", "industry"])
            idx_city = self._find_header_index(headers, ["Ciudad", "city"])
            idx_email = self._find_header_index(headers, ["Mail o IG", "email", "correo", "contact_email"])
            idx_phone = self._find_header_index(headers, ["Telefono", "Teléfono", "phone"])
            idx_send_date = self._find_header_index(headers, ["Fecha envio", "Fecha envío", "send_date"])
            idx_send_status = self._find_header_index(headers, ["Enviado?", "send_status", "estado envio"])
            idx_subject = self._find_header_index(headers, ["Asunto usado", "subject_used", "asunto"])
            idx_result = self._find_header_index(headers, ["Resultado", "result"])

            email_raw = self._safe_get(row, idx_email)
            return Lead(
                id=str(row_id),
                business_name=self._safe_get(row, idx_business),
                contact_name=self._safe_get(row, idx_contact),
                track=self._parse_track(self._safe_get(row, idx_track)),
                industry=self._safe_get(row, idx_industry),
                city=self._safe_get(row, idx_city),
                email=self._extract_email(email_raw),
                phone=self._safe_get(row, idx_phone) or None,
                send_date=self._parse_date(self._safe_get(row, idx_send_date)),
                send_status=self._parse_send_status(self._safe_get(row, idx_send_status)),
                subject_used=self._safe_get(row, idx_subject),
                result=self._safe_get(row, idx_result),
            )
        except Exception as e:
            logger.error(f"Error parseando lead: {e}")
            return None

    @staticmethod
    def _parse_send_status(raw_status: str) -> SendStatus:
        """Parsea distintos formatos de estado (Pendiente/Enviado/No/Sí)."""
        if not raw_status:
            return SendStatus.PENDING

        normalized = str(raw_status).strip().lower()
        if "enviado" in normalized:
            return SendStatus.SENT
        if "pendiente" in normalized:
            return SendStatus.PENDING
        if "rebot" in normalized:
            return SendStatus.BOUNCED
        if "respond" in normalized:
            return SendStatus.REPLIED

        mapping = {
            "pendiente": SendStatus.PENDING,
            "enviado": SendStatus.SENT,
            "rebotó": SendStatus.BOUNCED,
            "reboto": SendStatus.BOUNCED,
            "respondió": SendStatus.REPLIED,
            "respondio": SendStatus.REPLIED,
            "si": SendStatus.SENT,
            "sí": SendStatus.SENT,
            "yes": SendStatus.SENT,
            "true": SendStatus.SENT,
            "1": SendStatus.SENT,
            "no": SendStatus.PENDING,
            "false": SendStatus.PENDING,
            "0": SendStatus.PENDING,
        }

        if normalized in mapping:
            return mapping[normalized]

        try:
            return SendStatus(raw_status)
        except Exception:
            logger.warning("⚠️  Estado de envío desconocido '%s'. Se toma como Pendiente.", raw_status)
            return SendStatus.PENDING
    
    # ========== PRESUPUESTOS ==========
    
    def get_all_budgets(self) -> List[Budget]:
        """Obtiene todos los presupuestos."""
        rows = self.read_range(settings.google_sheet_budgets_range)
        if not rows or len(rows) < 2:
            return []
        
        budgets = []
        for i, row in enumerate(rows[1:], start=2):
            try:
                budget = self._row_to_budget(row, row_id=i)
                if budget:
                    budgets.append(budget)
            except Exception as e:
                logger.warning(f"⚠️  Error parseando presupuesto en fila {i}: {e}")
        
        return budgets
    
    def add_budget(self, budget: Budget) -> bool:
        """Añade un nuevo presupuesto."""
        row = budget.to_sheet_row()
        return self.write_range(
            settings.google_sheet_budgets_range,
            [row],
            append=True
        )
    
    def _row_to_budget(self, row: List[str], row_id: int) -> Optional[Budget]:
        """Convierte una fila a objeto Budget."""
        if len(row) < 6:
            return None
        
        try:
            return Budget(
                id=str(row_id),
                client_name=row[1] if len(row) > 1 else "",
                project_description=row[2] if len(row) > 2 else "",
                project_scope=row[3] if len(row) > 3 else "",
                total_price_ars=float(row[4]) if len(row) > 4 and row[4] else 0.0,
                currency=row[5] if len(row) > 5 else "ARS",
                status=BudgetStatus(row[6]) if len(row) > 6 and row[6] else BudgetStatus.DRAFT,
                notes=row[7] if len(row) > 7 else "",
            )
        except Exception as e:
            logger.error(f"Error parseando presupuesto: {e}")
            return None
    
    # ========== PRECIOS ==========
    
    def get_all_prices(self) -> List[Price]:
        """Obtiene tabla de precios base."""
        rows = self.read_range(settings.google_sheet_prices_range)
        if not rows or len(rows) < 2:
            return []
        
        prices = []
        for row in rows[1:]:
            try:
                if len(row) >= 2:
                    price = Price(
                        service=row[0],
                        base_price_ars=float(row[1]) if row[1] else 0.0,
                        description=row[2] if len(row) > 2 else "",
                        estimated_days=int(row[3]) if len(row) > 3 and row[3] else 0,
                    )
                    prices.append(price)
            except Exception as e:
                logger.warning(f"⚠️  Error parseando precio: {e}")
        
        return prices
    
    def update_prices(self, prices: List[Price]) -> bool:
        """Actualiza tabla de precios completa."""
        rows = [["Servicio", "Precio (ARS)", "Descripción", "Días"]]
        rows.extend([p.to_sheet_row() for p in prices])
        return self.write_range(settings.google_sheet_prices_range, rows, append=False)
    
    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        """Intenta parsear fecha de string."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str)
        except Exception:
            pass

        for fmt in ("%d/%m/%Y", "%d/%m/%y"):
            try:
                return datetime.strptime(date_str, fmt)
            except Exception:
                continue

        return None