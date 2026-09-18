"""
Loop de envío automático: envía 1 email cada N minutos.

Uso:
    python send_loop.py                       -> 1 email cada 5 min + 0-60s jitter
    python send_loop.py --jitter 0            -> intervalo exacto, sin random
    python send_loop.py --jitter 120          -> 5 min + 0-120s random
    python send_loop.py --interval 10 --unit m -> 1 email cada 10 min
    python send_loop.py --interval 2 --unit m -> intervalo en minutos
    python send_loop.py --max 10              -> corta después de 10 envíos exitosos
    python send_loop.py --once                -> envía uno solo y sale (igual que test_send_single_email.py)

El loop reutiliza la lógica de test_send_single_email.py:
- Busca el primer lead PENDIENTE con email válido
- Genera email personalizado con Gemini
- Envía por Gmail
- Marca como "Enviado" en Google Sheets

Detener con Ctrl+C. Si ya no quedan leads pendientes, el loop termina solo.
"""
import argparse
import asyncio
import os
import random
import signal
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from config.settings import Settings
from core.models import Email, SendStatus
from core.sheets_client import SheetsClient
from services.gmail_service import GmailService
from services.gemini_service import GeminiService


STOP = False


def _handle_stop(signum, frame):
    global STOP
    print("\n⏹️  Señal de stop recibida, terminando después del envío actual...")
    STOP = True


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Envia 1 email cada N minutos en loop.")
    p.add_argument("--interval", type=float, default=5,
                   help="Intervalo base entre envios (default: 5). Ver --unit.")
    p.add_argument("--unit", choices=["s", "m"], default="m",
                   help="'s' = segundos, 'm' = minutos (default: m).")
    p.add_argument("--max", dest="max_sends", type=int, default=0,
                   help="Corta tras N envios exitosos. 0 = sin limite (default: 0).")
    p.add_argument("--once", action="store_true",
                   help="Envia un solo email y sale.")
    p.add_argument("--dry-run", action="store_true",
                   help="No envia ni escribe en Sheets, solo muestra lead y preview.")
    p.add_argument("--jitter", type=float, default=60,
                   help="Jitter aleatorio maximo en segundos que se SUMA al intervalo "
                        "(default: 60). Ej: intervalo 300s + jitter 60 = espera 300-360s. "
                        "Usa --jitter 0 para desactivar.")
    p.add_argument("--min-interval", type=float, default=300,
                   help="Espera minima efectiva en segundos (default: 300 = 5 min). "
                        "Si base+jitter da menos, se sube a este minimo.")
    p.add_argument("--allow-short", action="store_true",
                   help="Permite intervalos menores al minimo (para tests).")
    return p.parse_args()


async def send_one(dry_run: bool = False) -> bool:
    """Envia UN email al primer lead pendiente. True si envio OK.

    False = no hay leads pendientes (el loop debe terminar).
    Excepcion = fallo el envio (el loop reintenta en el proximo ciclo).
    """
    settings = Settings()
    _ = settings  # usa .env / defaults
    sheets = SheetsClient(credentials_file='credentials.json')
    gmail = GmailService('credentials.json', 'token_gmail.json')
    gemini = GeminiService()

    leads = sheets.get_all_leads()
    if not leads:
        print("No hay leads en la Sheet")
        return False

    target_lead = None
    for lead in leads:
        if lead.send_status != SendStatus.SENT and lead.email and "@" in lead.email:
            target_lead = lead
            break

    if not target_lead:
        print("No hay leads pendientes con email valido")
        return False

    print(f"Lead: {target_lead.contact_name} <{target_lead.email}> | "
          f"{target_lead.business_name} | {target_lead.industry}")

    industry = target_lead.industry or ""
    email_body = gemini.generate_email_for_lead(
        lead_name=target_lead.contact_name,
        business_name=target_lead.business_name,
        industry=target_lead.industry,
        specific_note=target_lead.notes or "",
        template="pymes" if "pyme" in industry.lower() else "marketing",
    )

    email = Email(
        to=target_lead.email,
        subject="💾 Developer Freelance - Desarrollo Web",
        body=email_body,
    )

    if dry_run:
        print("[DRY-RUN] No se envia. Preview:")
        print(f"Asunto: {email.subject}")
        print("-" * 70)
        print(email_body)
        print("-" * 70)
        return True

    message_id = gmail.send_email(email)
    if not message_id:
        raise RuntimeError("Gmail no devolvio Message ID (envio fallo)")
    print(f"Enviado. Message ID: {message_id}")

    if not target_lead.id:
        raise RuntimeError("Enviado pero el lead no tiene row_id para Sheets")

    updated = sheets.update_send_status(
        row_id=int(target_lead.id),
        status=SendStatus.SENT,
        subject=email.subject,
    )
    if updated:
        print("Sheets actualizado a 'Enviado'")
    else:
        print("Enviado, pero Sheets no se pudo actualizar (revisar manual)")
    return True


async def sleep_interruptible(total_sec: float):
    waited = 0.0
    step = min(5.0, total_sec)
    while waited < total_sec and not STOP:
        chunk = min(step, total_sec - waited)
        await asyncio.sleep(chunk)
        waited += chunk


async def main() -> int:
    global STOP
    args = parse_args()

    interval_sec = args.interval * 60 if args.unit == "m" else args.interval
    if interval_sec <= 0:
        print("El intervalo debe ser > 0")
        return 2
    if not args.allow_short and not args.dry_run:
        if interval_sec < args.min_interval:
            print(f"Intervalo base {interval_sec:.0f}s < minimo {args.min_interval:.0f}s. "
                  f"Se sube al minimo de {args.min_interval/60:.1f} min.")
            interval_sec = args.min_interval

    if args.once:
        ok = await send_one(dry_run=args.dry_run)
        return 0 if ok else 1

    try:
        signal.signal(signal.SIGINT, _handle_stop)
        signal.signal(signal.SIGTERM, _handle_stop)
    except Exception:
        pass  # Windows / entornos sin SIGTERM

    unit_label = "min" if args.unit == "m" else "seg"
    print("=" * 70)
    print(f"LOOP DE ENVIO - 1 email cada {interval_sec/60:.1f} min "
          f"+ jitter 0-{args.jitter:g}s (minimo {args.min_interval:.0f}s)")
    print(f"   Base: {interval_sec:.0f}s | "
          f"Limite: {'sin limite' if not args.max_sends else args.max_sends} | "
          "Ctrl+C para detener")
    print("=" * 70)

    sent = 0
    iteration = 0

    while not STOP:
        iteration += 1
        print(f"Iteracion #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        failed = False
        try:
            ok = await send_one(dry_run=args.dry_run)
        except Exception as e:
            print(f"Error en iteracion #{iteration}: {e} - reintento en proximo ciclo.")
            import traceback
            traceback.print_exc()
            ok = False
            failed = True

        if ok:
            sent += 1
        elif not failed:
            print("No quedan leads pendientes. Fin del loop.")
            break

        if args.max_sends and sent >= args.max_sends:
            print(f"Limite alcanzado ({sent} envios). Fin del loop.")
            break

        if STOP:
            break

        print(f"Esperando {interval_sec:.0f}s hasta proximo envio... [Ctrl+C detiene]")
        jitter = random.uniform(0, args.jitter) if args.jitter > 0 else 0.0
        wait_sec = interval_sec + jitter
        if not args.allow_short and wait_sec < args.min_interval:
            wait_sec = args.min_interval
        print(f"Base {interval_sec:.0f}s + jitter {jitter:.0f}s = espera {wait_sec:.0f}s "
              f"({wait_sec/60:.1f} min)")
        try:
            await sleep_interruptible(wait_sec)
        except asyncio.CancelledError:
            break

    print("=" * 70)
    print(f"Loop terminado. Iteraciones: {iteration} | Enviados: {sent}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
