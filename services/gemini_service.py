"""
Gemini Service - Integración con Gemini API para generación de texto.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class GeminiService:
    """
    Servicio para generar contenido con Gemini.
    Por ahora usa templates, integrará API real cuando tengas key.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: API key de Gemini (opcional, fallback a templates)
        """
        self.api_key = api_key
        self.client = None
        
        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self.client = genai.GenerativeModel("gemini-1.5-flash")
                logger.info("✅ Gemini API configurada")
            except Exception as e:
                logger.warning(f"⚠️  Gemini API no disponible, usando templates: {e}")
    
    def generate_email_for_lead(self, 
                               lead_name: str,
                               business_name: str,
                               industry: str,
                               specific_note: str = "",
                               template: str = "pymes") -> str:
        """
        Genera body de mail personalizado.
        
        Args:
            lead_name: Nombre de la persona
            business_name: Nombre del negocio
            industry: Rubro (restaurante, inmobiliaria, etc.)
            specific_note: Algo específico del negocio que viste
            template: "pymes" o "marketing"
        
        Returns:
            Body del mail generado
        """
        if self.client:
            return self._generate_with_api(
                lead_name, business_name, industry, specific_note, template
            )
        else:
            return self._generate_with_template(
                lead_name, business_name, industry, specific_note, template
            )
    
    def _generate_with_api(self, lead_name, business_name, industry, 
                          specific_note, template) -> str:
        """Genera con Gemini API (cuando esté disponible)."""
        try:
            prompt = f"""
            Eres Germán Rodríguez, desarrollador web freelance especializado en {industry}.
            
            Genera un mail corto y personal para {lead_name} de {business_name}.
            
            Detalles específicos: {specific_note or 'Sin detalles extra'}
            
            Template: {template} ({'para dueños de PyMEs' if template == 'pymes' else 'para agencias de marketing'})
            
            El mail debe:
            - Mencionar algo específico del negocio
            - Ser corto (3-4 párrafos máximo)
            - No prometer precios
            - Terminar con invitación a conversar sin presión
            - Despedida: "Saludos, Germán Rodríguez"
            
            ⚠️  IMPORTANTE: No incluyas firma detallada - la firma se agregará automáticamente
            Devuelve SOLO el body del mail sin firma profesional, el sistema la agrega automáticamente.
            """
            
            response = self.client.generate_content(prompt)
            return response.text
        
        except Exception as e:
            logger.warning(f"Error con Gemini, fallback a template: {e}")
            return self._generate_with_template(
                lead_name, business_name, industry, specific_note, template
            )
    
    def _generate_with_template(self, lead_name, business_name, industry,
                               specific_note, template) -> str:
        """
        Fallback: genera desde template.
        
        ⚠️  IMPORTANTE: NO incluye firma aquí
        La firma se agrega automáticamente en GmailService.send_email()
        (igual que cuando redactas un mail en Gmail manualmente)
        """
        
        if template == "pymes":
            return f"""Hola {lead_name},

Estuve viendo {business_name} y me pareció {specific_note or "que tienen un buen posicionamiento"}.

Soy Germán Rodríguez, desarrollador web especializado en {industry}. He notado que {'no tienen presencia web propia' if not specific_note else 'su web podría mejorar mucho'}. En 2025, eso significa perder clientes potenciales que se van a la competencia que sí aparece bien en Google.

Trabajo con negocios como el tuyo para darles una web que convierte. Si te interesa, puedo mandarte en 5 minutos una idea concreta de cómo se vería y qué costaría. Sin compromiso.

Te dejo mi portafolio: https://germanrodriguez.ar/

Saludos,
Germán Rodríguez"""
        
        else:  # marketing
            return f"""Hola {lead_name},

Soy Germán Rodríguez, desarrollador web freelance. Trabajo con agencias y freelancers de marketing armando las webs, landings y sistemas que ustedes les prometen a sus clientes.

Vi que en {business_name} entregan proyectos web de calidad, y me gustaría ser esa opción de developer "de bolsillo" para cuando necesiten resolver algo rápido sin sobrecargar el equipo.

Te dejo mi portafolio: https://germanrodriguez.ar/

Si en algún momento necesitan un developer confiable, me encantaría colaborar.

Saludos,
Germán Rodríguez"""
    
    def generate_budget_proposal(self, client_name: str, 
                                project_description: str,
                                base_price: float) -> str:
        """
        Genera propuesta de presupuesto.
        
        Args:
            client_name: Nombre del cliente
            project_description: Descripción del proyecto
            base_price: Precio base en ARS
        
        Returns:
            Propuesta en HTML
        """
        if self.client:
            return self._generate_proposal_with_api(
                client_name, project_description, base_price
            )
        else:
            return self._generate_proposal_template(
                client_name, project_description, base_price
            )
    
    def _generate_proposal_with_api(self, client_name, project_description,
                                   base_price) -> str:
        """Genera propuesta con Gemini API."""
        try:
            prompt = f"""
            Genera una propuesta profesional de presupuesto en HTML para:
            
            Cliente: {client_name}
            Proyecto: {project_description}
            Presupuesto base: ${base_price:,.0f} ARS
            
            Incluye:
            - Descripción del alcance
            - Detalles técnicos
            - Precio desglosado
            - Plazo estimado
            - Términos de pago
            - Próximos pasos
            
            Usa un HTML profesional, elegante pero simple (sin CSS externo).
            """
            
            response = self.client.generate_content(prompt)
            return response.text
        
        except Exception as e:
            logger.warning(f"Error generando con Gemini: {e}")
            return self._generate_proposal_template(
                client_name, project_description, base_price
            )
    
    def _generate_proposal_template(self, client_name, project_description,
                                   base_price) -> str:
        """Template de propuesta."""
        return f"""<html>
<body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
    <h2>Propuesta de Presupuesto</h2>
    <p><strong>Cliente:</strong> {client_name}</p>
    <p><strong>Proyecto:</strong> {project_description}</p>
    
    <h3>Alcance</h3>
    <ul>
        <li>Desarrollo completo del proyecto</li>
        <li>Diseño responsivo (mobile, tablet, desktop)</li>
        <li>Testing y optimización</li>
        <li>Deploy en servidor</li>
    </ul>
    
    <h3>Presupuesto</h3>
    <p><strong>Monto Total: ${base_price:,.0f} ARS</strong></p>
    <p><em>50% al inicio del proyecto, 50% a la entrega</em></p>
    
    <h3>Plazo</h3>
    <p>2-3 semanas desde inicio</p>
    
    <h3>Próximos Pasos</h3>
    <ol>
        <li>Confirmás el presupuesto</li>
        <li>Acordamos cronograma detallado</li>
        <li>Comenzamos el desarrollo</li>
    </ol>
    
    <p><strong>Germán Rodríguez</strong></p>
    <p>Desarrollador Web Freelance<br>germanrodriguez.ar</p>
</body>
</html>"""
