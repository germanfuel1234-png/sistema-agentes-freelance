"""Cliente de enriquecimiento para SalesQL."""
import logging
from typing import Any, Dict

import httpx

from core.base_enricher import BaseEnricher

logger = logging.getLogger(__name__)


class SalesQLEnricher(BaseEnricher):
    """Implementación de enriquecimiento de leads usando SalesQL."""

    def __init__(self, api_key: str, endpoint: str = "https://api.salesql.com/v1/enrich"):
        self.api_key = (api_key or "").strip()
        self.endpoint = endpoint

    async def enrich_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        linkedin_url = lead_data.get("linkedin_url") or lead_data.get("linkedin")

        if not linkedin_url or not self.api_key:
            return lead_data

        if lead_data.get("email") and "@" in str(lead_data.get("email")):
            return lead_data

        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"profile_url": linkedin_url}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.endpoint, json=payload, headers=headers)
                if response.status_code in (402, 403, 429):
                    logger.warning(
                        "⚠️ SalesQL cuota/límite (%s). Fallback al siguiente proveedor.",
                        response.status_code,
                    )
                    return lead_data

                response.raise_for_status()
                data = response.json() or {}

            # Normaliza nombres de campos para no acoplar el agente al proveedor.
            lead_data["contact_name"] = data.get("name") or lead_data.get("contact_name") or lead_data.get("nombre")
            lead_data["nombre"] = lead_data.get("contact_name") or lead_data.get("nombre")
            lead_data["email"] = data.get("email") or lead_data.get("email")
            lead_data["phone"] = data.get("phone") or lead_data.get("phone")
        except Exception as e:
            logger.warning(
                "⚠️ Error enriqueciendo lead con SalesQL (%s): %s",
                lead_data.get("empresa") or lead_data.get("business_name") or "N/A",
                e,
            )

        return lead_data
