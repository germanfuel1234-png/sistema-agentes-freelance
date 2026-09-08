# 🔧 HABILITAR APIs - Guía Paso a Paso

## ⚠️ ESTADO ACTUAL

Tu proyecto tiene configurado:
- ✅ **credentials.json** - Presente
- ✅ **token_gmail.json** - Presente
- ❌ **Google Sheets API** - NO HABILITADA
- ❌ **Google Drive API** - NO HABILITADA

Sin estas APIs habilitadas, el sistema no puede:
- ❌ Leer tus leads de la planilla
- ❌ Registrar emails como "Enviados"
- ❌ Guardar presupuestos
- ❌ Agregar nuevos leads

---

## 🚀 PASOS PARA HABILITAR

### 1️⃣ Google Sheets API

**Paso 1.1 - Abre el enlace directo:**
```
https://console.developers.google.com/apis/api/sheets.googleapis.com/overview?project=1062678513752
```

**Paso 1.2 - Haz click en el botón ENABLE (Habilitar)**
- Verás un botón azul grande que dice "ENABLE"
- Hazle click

**Paso 1.3 - Espera a que se complete**
- Verás una animación de carga
- Espera a que termine

**Paso 1.4 - Confirma que está habilitada**
- Verás "Sheets API" con un check ✅
- El botón cambiará a "MANAGE" en lugar de "ENABLE"

---

### 2️⃣ Google Drive API

**Paso 2.1 - Abre el enlace directo:**
```
https://console.developers.google.com/apis/api/drive.googleapis.com/overview?project=1062678513752
```

**Paso 2.2 - Haz click en el botón ENABLE**
- Igual al paso anterior
- Hazle click

**Paso 2.3 - Espera a que se complete**
- Misma animación de carga
- Espera 2-3 minutos

**Paso 2.4 - Confirma que está habilitada**
- Verás "Drive API" con un check ✅
- El botón cambiará a "MANAGE"

---

## ⏱️ TIEMPOS IMPORTANTES

| Acción | Tiempo |
|--------|--------|
| Click ENABLE | Inmediato |
| Habilitación en Console | 5-30 segundos |
| Propagación a sistema | 2-3 minutos |
| Total | ~5 minutos |

**⚠️ IMPORTANTE:** Después de hacer click en ENABLE, **ESPERA 2-3 MINUTOS** antes de intentar usar el sistema.

---

## ✅ DESPUÉS DE HABILITAR

Una vez que ambas APIs estén habilitadas y hayan pasado 2-3 minutos, ejecuta:

```bash
cd /home/german/Escritorio/marketin/sistema_agentes_freelance
source venv/bin/activate
python test_send_single_email.py
```

**Resultado esperado:**
```
======================================================================
🚀 PRUEBA DE EMAIL - Enviar a UN lead
======================================================================

📋 Paso 1: Leyendo leads de tu Google Sheet...
✅ Encontrados X leads

📧 Paso 2: Buscando lead SIN email enviado...
✅ Lead seleccionado: Juan García López
   📧 Email: juan@example.com
   🏢 Empresa: Marketing Agency Pro
   📍 Rubro: Marketing

✉️  Paso 3: Generando email personalizado...
✅ Email generado

🚀 Paso 4: Enviando email por Gmail...
✅ Email enviado exitosamente!
   📨 Message ID: 18b7e7a1234567890

💾 Paso 5: Registrando en Google Sheets como 'Enviado'...
✅ Estado actualizado en Sheets

📊 RESUMEN DEL ENVÍO:
✅ Destinatario: Juan García López
✅ Email: juan@example.com
✅ Empresa: Marketing Agency Pro
✅ Estado en Sheets: ENVIADO
```

---

## 🆘 Troubleshooting

### Error: "The caller does not have permission"
**Causa:** Las APIs no están habilitadas  
**Solución:** 
1. Habilita Google Sheets API (enlace arriba)
2. Habilita Google Drive API (enlace arriba)
3. Espera 2-3 minutos
4. Intenta de nuevo

### Error: "Google Sheets API has not been used in project"
**Causa:** Google acaba de habilitar pero no ha propagado  
**Solución:**
1. Espera 3 minutos más
2. Intenta de nuevo

### El email se envía pero no aparece en la Sheet
**Causa:** El acceso a Drive no está habilitado  
**Solución:**
1. Habilita Google Drive API
2. Espera 2-3 minutos
3. Intenta de nuevo

---

## 🎓 ¿QUÉ HACE CADA API?

### Google Sheets API
- ✅ Leer datos de tu Sheet (`leads_tracking`, `emails_sent`, etc.)
- ✅ Escribir nuevos leads
- ✅ Actualizar estados ("Enviado", "Respondió", etc.)
- ✅ Crear presupuestos

### Google Drive API
- ✅ Acceder a los archivos en tu Google Drive
- ✅ Validar permisos para leer/escribir
- ✅ Gestionar el acceso a la Sheet compartida

**Ambas son necesarias** para que funcione el sistema completo.

---

## 📊 FLUJO COMPLETO

```
1. HABILITAR APIs (5 min - UNA SOLA VEZ)
   ↓
2. EJECUTAR python test_send_single_email.py
   ↓
3. SISTEMA LEE LOS LEADS DE TU SHEET
   ↓
4. SISTEMA GENERA EMAIL PERSONALIZADO
   ↓
5. SISTEMA ENVÍA POR GMAIL
   ↓
6. SISTEMA REGISTRA EN SHEETS COMO "ENVIADO"
   ↓
7. ✅ COMPLETO - Email enviado y trackeado
```

---

## 🔗 ENLACES DIRECTOS

**Google Sheets API:**
```
https://console.developers.google.com/apis/api/sheets.googleapis.com/overview?project=1062678513752
```

**Google Drive API:**
```
https://console.developers.google.com/apis/api/drive.googleapis.com/overview?project=1062678513752
```

**Google Cloud Console (Proyecto):**
```
https://console.cloud.google.com/apis/dashboard?project=1062678513752
```

---

**¡Una vez habilitadas, el sistema funcionará automáticamente! 🚀**
