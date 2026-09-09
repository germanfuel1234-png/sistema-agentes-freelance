"""Cliente de enriquecimiento para Hunter.io."""
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

from core.base_enricher import BaseEnricher

logger = logging.getLogger(__name__)


class HunterEnricher(BaseEnricher):
    """Implementación de enriquecimiento de leads usando Hunter Email Finder."""

    def __init__(self, api_key: str, endpoint: str = "https://api.hunter.io/v2/email-finder"):
        self.api_key = (api_key or "").strip()
        self.endpoint = endpoint

    @staticmethod
    def _extract_domain(lead_data: Dict[str, Any]) -> Optional[str]:
        raw_domain = (lead_data.get("website_domain") or "").strip()
        if raw_domain:
            return raw_domain.replace("https://", "").replace("http://", "").strip("/")

        website = (lead_data.get("website") or "").strip()
        if not website:
            return None

        parsed = urlparse(website if "://" in website else f"https://{website}")
        return (parsed.netloc or "").replace("www.", "") or None

    async def enrich_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            return lead_data

        if lead_data.get("email") and "@" in str(lead_data.get("email")):
            return lead_data

        domain = self._extract_domain(lead_data)
        full_name = (lead_data.get("contact_name") or lead_data.get("nombre") or "").strip()
        if not domain or not full_name:
            return lead_data

        params = {
            "domain": domain,
            "full_name": full_name,
            "api_key": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.endpoint, params=params)

            if response.status_code == 200:
                data = (response.json() or {}).get("data", {})
                if data.get("email"):
                    lead_data["email"] = data.get("email")
                    if not lead_data.get("contact_name"):
                        lead_data["contact_name"] = data.get("first_name") or full_name
                    if not lead_data.get("phone") and data.get("phone_number"):
                        lead_data["phone"] = data.get("phone_number")
            elif response.status_code in (402, 403, 429):
                logger.warning(
                    "⚠️ Hunter.io cuota/límite (%s). Fallback al siguiente proveedor.",
                    response.status_code,
                )
            else:
                logger.warning("⚠️ Hunter.io respondió %s", response.status_code)
        except Exception as e:
            logger.warning("⚠️ Error consultando Hunter.io: %s", e)

        return lead_data
