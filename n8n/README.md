# n8n local (Docker)

Levanta n8n + su base de datos Postgres en contenedores Docker, en la
PC local. Es la misma configuración que se va a usar el día que esto
se mueva a un servidor (Hostinger VPS u otra opción) - solo cambian
las variables de `.env` (dominio en vez de localhost), no el
`docker-compose.yml`.

## Requisito: Docker instalado

Este repo no instala Docker por vos (necesita `sudo`). Instalarlo una
sola vez con el script oficial:

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

Después de correr `usermod`, cerrar sesión y volver a entrar (o
reiniciar) para que el usuario quede en el grupo `docker` sin
necesitar `sudo` en cada comando. Confirmar con:

```bash
docker --version
docker compose version
```

## Uso

El `.env` con las claves ya está generado (no se sube a git). Si hay
que rehacerlo, copiar `.env.example` a `.env` y completar los valores.

```bash
cd sistema_agentes_freelance/n8n
docker compose up -d        # levanta n8n + Postgres en background
docker compose logs -f n8n  # ver logs en vivo
docker compose ps           # confirmar que los dos servicios están "healthy"/"running"
```

Una vez arriba, entrar a **http://localhost:5678** - la primera vez
n8n pide crear un usuario/contraseña propio (queda guardado en la base
de Postgres, no en el `.env`).

## Parar / reiniciar

```bash
docker compose stop         # frena los contenedores, no borra datos
docker compose up -d        # los vuelve a levantar
docker compose down         # frena y borra los contenedores (los datos
                             # persisten en los volúmenes con nombre,
                             # no se pierden)
```

## El servicio `runner` (Python/Chromium/Playwright)

La imagen oficial de n8n es "hardened" - no tiene Python, Chrome, ni
gestor de paquetes adentro (a propósito, por seguridad). Por eso hay un
**tercer contenedor**, `runner`, con su propia imagen (Python + Node +
Chromium + Playwright) que expone una API HTTP mínima para correr los
scripts pesados del proyecto. Nunca se publica a la LAN ni a internet -
solo es alcanzable *dentro* de la red interna de Docker Compose.

Desde un nodo **HTTP Request** en n8n (nunca `Execute Command`):

```
POST http://runner:8000/presupuesto
Content-Type: application/json

{
  "cliente": "Nombre del cliente",
  "url": "https://sitio.com",
  "estrategia": "mobile"
}
```

Devuelve `{"ok": true, "stdout": "..."}` y deja el HTML generado en
`presupuestos_generados/` (accesible en el host tal cual, no solo
adentro del contenedor - está montado como volumen).

Chequeo rápido de que está vivo: `GET http://runner:8000/health`.

**Nota**: los archivos que genera el `runner` (los HTML de
`presupuestos_generados/`) quedan con dueño `root` en el host, porque
el contenedor corre como root por dentro. No es un problema de
seguridad (es tu propia PC), pero si querés borrarlos/editarlos a mano
puede hacer falta `sudo`.

## Cuando se arme el túnel de Cloudflare (Fase 2)

Editar `.env`: cambiar `N8N_HOST`, `N8N_PROTOCOL` y `WEBHOOK_URL` por
el dominio real del túnel, y correr `docker compose up -d` de nuevo
para que tome los cambios. El puerto sigue publicado solo en
`127.0.0.1:5678` - `cloudflared` corre en la misma máquina y apunta ahí,
no hace falta exponerlo a la LAN.
