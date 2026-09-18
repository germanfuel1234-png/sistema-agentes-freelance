# Imagen "a medida" con todo lo que n8n (hardened, sin gestor de
# paquetes) no tiene: Python, Chromium (para Lighthouse) y Playwright
# (para el PDF del presupuesto). No se toca la imagen oficial de n8n -
# esto corre en un contenedor separado, solo alcanzable desde la red
# interna de Docker Compose.
#
# Build context = raíz del proyecto (marketin/), ver docker-compose.yml.
FROM node:20-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv chromium \
    && rm -rf /var/lib/apt/lists/*

# Lighthouse (agente_presupuesto_seo.py) busca un Chrome real para
# lanzar - le apuntamos al Chromium instalado por apt arriba.
ENV CHROME_PATH=/usr/bin/chromium

WORKDIR /app

COPY sistema_agentes_freelance/requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt \
    && pip3 install --no-cache-dir --break-system-packages playwright \
    && playwright install --with-deps chromium

COPY sistema_agentes_freelance/n8n/runner/app.py /app/app.py

EXPOSE 8000
CMD ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
