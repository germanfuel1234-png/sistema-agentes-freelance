"""Asistente interactivo: posteos ORGANICOS de LinkedIn/X -> Google Sheets.

REGLA ESTRICTA: rechaza URLs de portales de empleo (Freelancer, Upwork,
Workana, Fiverr, Computrabajo, etc.). Solo acepta linkedin.com/posts y
x.com | twitter.com/status.

Ejecutar desde la raiz del repo:
    python busqueda_linkedin/linkedin_manual_busqueda.py            (interactivo)
    python busqueda_linkedin/linkedin_manual_busqueda.py --list     (solo consultas)
"""
import sys

# importar el actualizador ya inserta ROOT en sys.path (config/, core/)
import actualizar_oportunidades_freelance as aof
from core.sheets_client import SheetsClient

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TAB = "oportunidades_freelance"
SKILL_HINT = ("desarrollo web", "SEO tecnico", "analisis de sistemas",
              "Python", "PHP", "Dart", "Kotlin")


def imprimir_consultas():
    print("=" * 78)
    print("CONSULTAS (ventana: ULTIMOS 7 DIAS) - SOLO redes sociales, sin portales")
    print("=" * 78)
    print("\n-- PASO 1: LinkedIn LOGUEADO -> Buscar > Publicaciones > Fecha: 'Ultima semana'")
    for i, fp in enumerate(aof.FOOTPRINTS, 1):
        kw = "%22" + fp.replace(" ", "%20") + "%22%20(%22desarrollo%20web%22%20OR%20SEO%20OR%20Python%20OR%20PHP%20OR%20Dart%20OR%20Kotlin)"
        print("%d. https://www.linkedin.com/search/results/content/?keywords=%s" % (i, kw))
    print("\n-- PASO 2: X (Twitter) en vivo --")
    for i, fp in enumerate(aof.FOOTPRINTS, 1):
        print("%d. https://x.com/search?q=%s+(%%22desarrollo+web%%22+OR+SEO+OR+Python+OR+PHP)&f=live"
              % (i, fp.replace(" ", "+")))
    print("\nREGLA ESTRICTA: se descartan automaticamente URLs de portales de empleo")
    print("y todo lo que no sea linkedin.com o x.com/twitter.com.")
    print("Habilidades a cruzar: %s" % ", ".join(SKILL_HINT))


def pedir_urls():
    items = []
    print("\n-- PASO 3: pega las URLs de los posteos (Enter vacio para terminar) --")
    while True:
        try:
            u = input("  URL> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not u:
            break
        if aof.es_portal(u):
            print("    X REGLA ESTRICTA: portal de empleo prohibido -> descartada.")
            continue
        if not aof.es_red_social(u):
            print("    X Solo se aceptan posteos de LinkedIn/X -> descartada.")
            continue
        autor, fecha, _ = aof.enrich(u, "")
        items.append({
            "link": u,
            "empresa": autor,
            "fecha": fecha,
            "req": "Pegado a mano: revisar match %s." % ", ".join(SKILL_HINT),
            "fuente": "LinkedIn" if "linkedin.com" in u else "X",
            "frase": "",
            "skills": [],
        })
        print("    OK %s | %s" % (autor, fecha or "fecha a confirmar"))
    return items


def main(argv):
    if "--list" in argv:
        imprimir_consultas()
        return 0
    imprimir_consultas()
    items = pedir_urls()
    if not items:
        print("\nSin URLs para guardar.")
        return 1
    r = input("\nGuardar %d en la pestana '%s'? (s/n): " % (len(items), TAB)).strip().lower()
    if r != "s":
        print("Cancelado, no se escribio nada.")
        return 0
    nuevos, base = aof.guardar(items, TAB, SheetsClient(aof.CRED_PATH))
    print("%d guardadas | %d ya existian" % (len(nuevos), base))
    print("Ver: https://docs.google.com/spreadsheets/d/%s" % aof.SPREADSHEET_ID)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
