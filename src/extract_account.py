"""
Extrae cuentas (Account) de Salesforce y las guarda en la carpeta raw/
con metadatos de ejecucion, sin modificar los datos originales.

Uso (desde la raiz de tu repo):
    python scripts/extraer_account.py
    python scripts/extraer_account.py --org my-org
    python scripts/extraer_account.py --desde-archivo cuentas.json

Resultado:
    raw/salesforce/account/year=2026/month=11/day=02/account_153045.json
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------- Configuracion ----------------
ORG_ALIAS = "my-org"          # el alias que usaste en sf org login web
OBJETO = "Account"
CONSULTA = (
    "SELECT Id, Name, Type, Industry, BillingCity, BillingCountry, "
    "CreatedDate, SystemModstamp FROM Account"
)
RUTA_SF_WINDOWS = r"C:\Program Files\sf\bin\sf.cmd"
# Carpeta raiz del repo: una carpeta arriba de /scripts
# (si guardas este archivo en la raiz del repo, cambia a Path(__file__).parent)
RAIZ = Path(__file__).resolve().parent.parent
# -----------------------------------------------


def encontrar_sf():
    """Busca el programa sf en el PATH; si no esta, usa la ruta de Windows."""
    ruta = shutil.which("sf")
    if ruta:
        return ruta
    if Path(RUTA_SF_WINDOWS).exists():
        return RUTA_SF_WINDOWS
    sys.exit("No encontre el Salesforce CLI (sf). Revisa que este instalado.")


def extraer_desde_salesforce(org):
    """Ejecuta la consulta con el CLI y devuelve la lista de registros."""
    comando = [
        encontrar_sf(), "data", "query",
        "--query", CONSULTA,
        "--target-org", org,
        "--json",
    ]
    resultado = subprocess.run(
        comando, capture_output=True, text=True, encoding="utf-8"
    )
    try:
        respuesta = json.loads(resultado.stdout)
    except json.JSONDecodeError:
        sys.exit(f"Error al leer la respuesta de sf:\n{resultado.stdout}\n{resultado.stderr}")

    if respuesta.get("status") != 0:
        sys.exit(f"Salesforce devolvio un error:\n{respuesta.get('message', respuesta)}")

    return respuesta["result"]["records"]


def leer_desde_archivo(ruta):
    """Lee registros de un JSON que ya sacaste antes con sf data query."""
    with open(ruta, encoding="utf-8-sig") as f:  # utf-8-sig tolera el BOM de PowerShell
        contenido = json.load(f)
    return contenido["result"]["records"]


def guardar_raw(registros):
    """Envuelve los registros con metadata y los guarda en la estructura raw/."""
    ahora = datetime.now(timezone.utc)
    run_id = ahora.strftime("%Y%m%dT%H%M%SZ")

    documento = {
        "metadata": {
            "source": f"salesforce/{OBJETO}",
            "ingested_at_utc": ahora.isoformat(timespec="seconds"),
            "record_count": len(registros),
            "run_id": run_id,
        },
        "data": registros,  # datos originales, sin tocar
    }

    carpeta = (
        RAIZ / "raw" / "salesforce" / OBJETO.lower()
        / f"year={ahora:%Y}" / f"month={ahora:%m}" / f"day={ahora:%d}"
    )
    carpeta.mkdir(parents=True, exist_ok=True)

    archivo = carpeta / f"{OBJETO.lower()}_{ahora:%H%M%S}.json"
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(documento, f, ensure_ascii=False, indent=2)

    return archivo, run_id


def main():
    parser = argparse.ArgumentParser(description="Extrae Account de Salesforce a raw/")
    parser.add_argument("--org", default=ORG_ALIAS, help="alias de la org de Salesforce")
    parser.add_argument("--desde-archivo", help="usar un JSON existente en vez de consultar Salesforce")
    args = parser.parse_args()

    if args.desde_archivo:
        print(f"Leyendo registros de {args.desde_archivo} ...")
        registros = leer_desde_archivo(args.desde_archivo)
    else:
        print(f"Consultando Salesforce (org: {args.org}) ...")
        registros = extraer_desde_salesforce(args.org)

    archivo, run_id = guardar_raw(registros)
    print(f"Listo. run_id: {run_id}")
    print(f"{len(registros)} registros guardados en:\n{archivo}")


if __name__ == "__main__":
    main()