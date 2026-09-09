"""Enricher en cascada con fallback entre múltiples proveedores."""
import logging
from typing import Any, Dict, List

from core.base_enricher import BaseEnricher

logger = logging.getLogger(__name__)


class FallbackEnricher(BaseEnricher):
    """
    Recorre proveedores en orden y se detiene cuando obtiene email válido.
    Si un proveedor falla o no completa email, continúa con el siguiente.
    """

    def __init__(self, providers: List[BaseEnricher]):
        self.providers = providers

    async def enrich_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        if lead_data.get("email") and "@" in str(lead_data.get("email")):
            return lead_data

        for provider in self.providers:
            provider_name = provider.__class__.__name__
            try:
                lead_data = await provider.enrich_lead(lead_data)
                if lead_data.get("email") and "@" in str(lead_data.get("email")):
                    logger.info("✅ Email enriquecido por %s", provider_name)
                    return lead_data
            except Exception as e:
                logger.warning("⚠️ Provider %s falló. Continuando fallback: %s", provider_name, e)

        return lead_data
