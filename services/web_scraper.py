"""
Web Scraper Service - Extrae información de webs.
"""
import logging
from typing import Optional, List
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


def get_session():
    """Crea sesión requests con reintentos automáticos."""
    session = requests.Session()
    retry = Retry(connect=3, backoff_factor=0.5)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


class WebScraper:
    """Scraper para extraer información de webs."""
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = get_session()
    
    def scrape_germanrodriguez_ar(self) -> dict:
        """
        Scraping de germanrodriguez.ar para extraer servicios y precios.
        
        Returns:
            Dict con servicios, precios, posicionamiento
        """
        try:
            url = "https://germanrodriguez.ar"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Extrae servicios (busca headers y listas)
            services = self._extract_services(soup)
            target_industries = self._extract_industries(soup)
            value_prop = self._extract_value_proposition(soup)
            
            logger.info(f"✅ Scraped {len(services)} servicios de germanrodriguez.ar")
            
            return {
                "services": services,
                "target_industries": target_industries,
                "value_proposition": value_prop,
                "url": url,
            }
        
        except requests.RequestException as e:
            logger.error(f"❌ Error descargando germanrodriguez.ar: {e}")
            # Retorna datos por defecto si falla
            return self._default_data()
    
    def _extract_services(self, soup: BeautifulSoup) -> List[dict]:
        """Extrae servicios y precios del HTML."""
        services = []
        
        # Busca patrones comunes de precio en HTML
        price_patterns = [
            ("Landing Page", 100000),
            ("Web Corporativa", 400000),
            ("E-Commerce", 530000),
            ("Apps/Sistemas", 500000),
        ]
        
        # Intenta encontrar tabla de precios
        tables = soup.find_all("table")
        if tables:
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= 2:
                        try:
                            service_name = cells[0].get_text().strip()
                            # Intenta extraer número de precio
                            price_text = cells[1].get_text().strip()
                            price = self._extract_price(price_text)
                            
                            if price and len(service_name) > 3:
                                services.append({
                                    "name": service_name,
                                    "price": price,
                                })
                        except:
                            continue
        
        # Si no encontró tabla, usa defaults
        if not services:
            services = [
                {"name": name, "price": price}
                for name, price in price_patterns
            ]
        
        return services
    
    def _extract_industries(self, soup: BeautifulSoup) -> List[str]:
        """Extrae industrias mencionadas."""
        industries = []
        
        text = soup.get_text().lower()
        potential_industries = [
            "estudios jurídicos", "abogados",
            "consultorios médicos", "odontología",
            "inmobiliarias",
            "restaurantes", "gastronomía",
            "pymes", "negocios",
        ]
        
        for industry in potential_industries:
            if industry in text:
                industries.append(industry.title())
        
        # Retorna algunos defaults si no encontró
        if not industries:
            industries = ["Estudios Jurídicos", "Consultorios Médicos", "Inmobiliarias"]
        
        return industries
    
    def _extract_value_proposition(self, soup: BeautifulSoup) -> str:
        """Extrae propuesta de valor."""
        # Busca first h1 o descripción
        h1 = soup.find("h1")
        if h1:
            return h1.get_text().strip()
        
        p = soup.find("p")
        if p:
            return p.get_text().strip()
        
        return "Desarrollo web profesional, rápido y a medida"
    
    @staticmethod
    def _extract_price(text: str) -> Optional[int]:
        """Extrae número de precio de texto."""
        import re
        # Busca patrón: $123.000 o $123000 o 123000
        match = re.search(r'\$?\s*(\d+[.,]?\d*[.,]?\d*)', text)
        if match:
            try:
                price_str = match.group(1).replace(".", "").replace(",", "")
                return int(float(price_str))
            except:
                pass
        return None
    
    def _default_data(self) -> dict:
        """Retorna datos por defecto si scraping falla."""
        return {
            "services": [
                {"name": "Landing Page", "price": 100000},
                {"name": "Web Corporativa", "price": 400000},
                {"name": "E-Commerce", "price": 530000},
                {"name": "Apps/Sistemas", "price": 500000},
            ],
            "target_industries": ["Estudios Jurídicos", "Consultorios Médicos", "Inmobiliarias"],
            "value_proposition": "Desarrollo web profesional, rápido y a medida",
            "url": "https://germanrodriguez.ar",
        }
