"""Interfaces base para enriquecimiento de leads."""
from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseEnricher(ABC):
    """Interfaz para proveedores de enriquecimiento de leads."""

    @abstractmethod
    async def enrich_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Recibe un lead parcial y devuelve el lead enriquecido."""
        raise NotImplementedError


class NoopEnricher(BaseEnricher):
    """Enricher nulo para mantener compatibilidad sin proveedor externo."""

    async def enrich_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        return lead_data
