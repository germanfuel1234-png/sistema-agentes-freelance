# 🚀 Agent 1B - Advanced Lead Search

## 📋 Descripción

**Agent 1B** es un agente especializado que busca leads en **múltiples fuentes** (LinkedIn, PyMEs, Instagram) de **España y Latam** y agrega automáticamente los contactos a tu Google Sheet.

**Lo mejor:** Solo necesitas **nombre + email**. Nada de datos innecesarios.

---

## 🎯 Qué hace

```
LinkedIn → Busca marketing managers, community managers, agencias
    ↓
PyMEs → Busca directorios de empresas marketing (España y Latam)
    ↓
Instagram → Busca perfiles de marketing y agencias digitales
    ↓
Consolida → Elimina duplicados automáticamente
    ↓
Sheets → AGREGA DIRECTAMENTE a tu planilla (sin aprobación)
```

---

## 🌍 Cobertura Geográfica

### Latam
- ✅ Argentina
- ✅ Chile
- ✅ Colombia
- ✅ México
- ✅ Perú
- ✅ Bolivia
- ✅ Paraguay
- ✅ Uruguay
- ✅ Ecuador
- ✅ Venezuela

### Europa
- ✅ España

---

## 🔧 Setup

### 1. Habilitar Google Sheets API

Google Sheets API debe estar HABILITADO en tu proyecto Google Cloud.

**Pasos:**

1. Abre: [Google Cloud Console - Sheets API](https://console.developers.google.com/apis/api/sheets.googleapis.com/overview?project=1062678513752)
2. Click en el botón **ENABLE** (Habilitar)
3. Espera 2-3 minutos para que se propague
4. Listo ✅

---

## 💻 Ejecutar Agent 1B

### Opción 1: Script de Prueba (Recomendado para empezar)

```bash
cd /home/german/Escritorio/marketin/sistema_agentes_freelance
source venv/bin/activate
python test_agent_1b.py
```

**Output esperado:**
```
======================================================================
🚀 Agent 1B - Advanced Lead Search (Multi-fuente)
======================================================================

📊 RESULTADOS:
✅ Total leads encontrados: 45
📱 Fuentes: LinkedIn, PyMEs, Instagram
🔄 Duplicados removidos: 5
💾 Agregados a Sheets: Sí (automático)

📋 LEADS AGREGADOS:

1. Juan García López
   📧 juan.garcia@marketingagency.com
   🏢 Marketing Agency Pro
   📍 LinkedIn

2. María Rodríguez
   📧 maria.r@agenciadigital.es
   🏢 Agencia Digital España
   📍 PyMEs

[...]

======================================================================
✅ ¡Agent 1B completado exitosamente!
======================================================================
```

### Opción 2: Integrado en el flujo completo (run_agents.py)

```bash
python run_agents.py
```

Agent 1B se ejecutará automáticamente entre los otros agentes.

---

## 📊 Datos que se guardan en Sheets

En la pestaña `leads_tracking`, Agent 1B agrega:

| Campo | Contenido | Ejemplo |
|-------|-----------|---------|
| Negocio | Empresa o nombre | "Marketing Pro SRL" |
| Contacto | Nombre de la persona | "Juan García López" |
| Email | **EMAIL DEL CONTACTO** | "juan@example.com" |
| Rubro | Siempre "Marketing" | "Marketing" |
| País | País detectado | "Argentina" |
| Fuente | De dónde vino | "LinkedIn / PyMEs / Instagram" |
| Estado | Siempre "Pendiente Outreach" | "Pendiente Outreach" |

**Nota:** Se almacenan SOLO los datos esenciales: nombre + email. Sin ruido.

---

## 🔄 Consolidación de Duplicados

Si el mismo email aparece en múltiples fuentes, Agent 1B lo detecta y lo agrega **una sola vez**.

Ejemplo:
```
LinkedIn: juan.garcia@example.com
Instagram: juan.garcia@example.com
PyMEs: juan.garcia@example.com

Resultado en Sheets: 1 registro único ✅
```

---

## 🚀 Uso en Producción

Una vez que Google Sheets API esté habilitada, puedes:

### Ejecutar diariamente (búsqueda fresca)
```bash
# En crontab (Linux/Mac)
0 9 * * * cd /path/to/proyecto && source venv/bin/activate && python test_agent_1b.py
```

### Integrar con otros agentes
Agent 1B está integrado en `run_agents.py`:
- **Agent 0:** Estudia tu web (germanrodriguez.ar)
- **Agent 1:** Busca leads básico
- **Agent 1B:** Busca leads multi-fuente ← TÚ ERES AQUÍ
- **Agent 4:** Supervisa el sistema
- **Agent 2:** Envía emails (con aprobación)
- **Agent 3:** Genera presupuestos (con aprobación)

---

## 📝 Configuración (Opcional)

En `services/advanced_search_service.py` puedes ajustar:

```python
# Aumentar/disminuir cantidad de resultados por fuente
linkedin_results = self.search_service.search_linkedin_professionals(
    keywords="marketing manager, community manager",
    region="latam",
    limit=15  # ← Cambiar aquí (default: 15)
)

# Cambiar regiones de búsqueda
search_instagram_marketing_profiles(
    region="latam",  # o "spain"
    limit=20
)
```

---

## ✅ Checklist de Implementación

- [x] Agent 1B creado y funcional
- [x] Búsqueda en LinkedIn integrada
- [x] Búsqueda en PyMEs integrada
- [x] Búsqueda en Instagram integrada
- [x] Consolidación de duplicados
- [x] Integración con Google Sheets
- [x] Test script listo
- [ ] **PENDIENTE:** Habilitar Google Sheets API en Google Cloud Console
- [ ] Ejecutar y validar primeros resultados

---

## 🎓 Próximos Pasos

1. **Habilita Google Sheets API** (5 min)
2. **Ejecuta `python test_agent_1b.py`** para ver los primeros leads
3. **Verifica en tu Google Sheet** que los leads se agregaron correctamente
4. **Personaliza** los keywords de búsqueda si lo necesitas
5. **Integra con Agent 2** para empezar a enviar emails automáticamente

---

## 🐛 Troubleshooting

### Error: "Google Sheets API has not been used in project"
✅ **Solución:** Habilita la API en Google Cloud Console (link arriba)

### Error: "Authentication required"
✅ **Solución:** Asegúrate que `credentials.json` existe en la carpeta raíz

### Error: "No leads found"
✅ **Solución:** Los leads están simulados. En producción, integra APIs reales de LinkedIn, etc.

---

## 📞 Soporte

Si tienes preguntas:
- Revisa [SETUP.md](./SETUP.md) para configuración general
- Revisa [README.md](./README.md) para arquitectura del sistema
- Mira los logs en `test_agent_1b.py` para debugging

---

**¡Listo para encontrar leads! 🚀**
