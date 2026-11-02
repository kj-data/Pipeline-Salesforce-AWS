"""
Lee TODOS los archivos de raw/salesforce/account/, los limpia con pandas
y guarda el resultado en processed/salesforce/account/.

Los archivos de raw/ nunca se modifican.

Uso (desde la raiz de tu repo):
    python src/process_account.py

Requiere:
    pip install pandas pyarrow
"""

import json
import sys
from pathlib import Path

import pandas as pd

# ---------------- Configuracion ----------------
RAIZ = Path(__file__).resolve().parent.parent   # raiz del repo (una carpeta arriba de /src)
CARPETA_RAW = RAIZ / "raw" / "salesforce" / "account"
CARPETA_PROCESSED = RAIZ / "processed" / "salesforce" / "account"

# Correcciones de errores de escritura que encontraste en los datos.
# Las claves van en minuscula. Agrega aqui los que vayas descubriendo.
CORRECCIONES_INDUSTRY = {
    "technolgy": "Technology",
}

COLUMNAS_TEXTO = ["Name", "Type", "Industry", "BillingCity", "BillingCountry"]
COLUMNAS_FECHA = ["CreatedDate", "SystemModstamp"]
# -----------------------------------------------


def cargar_raw():
    """Lee todos los JSON de raw y devuelve un DataFrame con todos los registros."""
    archivos = sorted(CARPETA_RAW.rglob("account_*.json"))
    if not archivos:
        sys.exit(f"No encontre archivos en {CARPETA_RAW}. Corre primero extract_account.py")

    partes = []
    for archivo in archivos:
        with open(archivo, encoding="utf-8") as f:
            contenido = json.load(f)

        df = pd.DataFrame(contenido["data"])
        # Guardamos de que corrida y archivo vino cada fila (trazabilidad)
        df["_run_id"] = contenido["metadata"]["run_id"]
        df["_ingested_at_utc"] = contenido["metadata"]["ingested_at_utc"]
        df["_source_file"] = archivo.name
        partes.append(df)

    print(f"Archivos leidos: {len(archivos)}")
    return pd.concat(partes, ignore_index=True)


def limpiar(df):
    """Aplica la limpieza y devuelve un DataFrame nuevo."""
    df = df.copy()
    filas_inicio = len(df)

    # 1. 'attributes' es un diccionario tecnico de Salesforce, no sirve para analisis
    df = df.drop(columns=["attributes"], errors="ignore")

    # 2. Quitar espacios sobrantes en los textos
    for col in COLUMNAS_TEXTO:
        if col in df.columns:
            df[col] = df[col].str.strip()

    # 3. Industry: unificar mayusculas/minusculas y corregir errores de escritura
    if "Industry" in df.columns:
        df["Industry"] = df["Industry"].str.lower().replace(CORRECCIONES_INDUSTRY)
        df["Industry"] = df["Industry"].str.title()

    # 4. Convertir las fechas de texto a fecha real
    for col in COLUMNAS_FECHA:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True)
    df["_ingested_at_utc"] = pd.to_datetime(df["_ingested_at_utc"], utc=True)

    # 5. Quitar duplicados: una fila por Id, la version mas reciente
    df = df.sort_values(["SystemModstamp", "_ingested_at_utc"])
    df = df.drop_duplicates(subset="Id", keep="last")
    df = df.sort_values("Name").reset_index(drop=True)

    print(f"Filas antes: {filas_inicio} | despues de quitar duplicados: {len(df)}")
    return df


def reporte_calidad(df):
    """Muestra un resumen rapido de nulos y valores de Industry."""
    print("\n--- Nulos por columna ---")
    nulos = df.isna().sum()
    print(nulos[nulos > 0].to_string() if nulos.any() else "Sin nulos")

    if "Industry" in df.columns:
        print("\n--- Valores de Industry ---")
        print(df["Industry"].value_counts(dropna=False).to_string())


def guardar(df):
    """Guarda el resultado en CSV y, si se puede, en Parquet."""
    CARPETA_PROCESSED.mkdir(parents=True, exist_ok=True)

    ruta_csv = CARPETA_PROCESSED / "account_clean.csv"
    df.to_csv(ruta_csv, index=False, encoding="utf-8")
    print(f"\nGuardado: {ruta_csv}")

    try:
        ruta_parquet = CARPETA_PROCESSED / "account_clean.parquet"
        df.to_parquet(ruta_parquet, index=False)
        print(f"Guardado: {ruta_parquet}")
    except ImportError:
        print("No se guardo Parquet (falta 'pyarrow'). Instala con: pip install pyarrow")


def main():
    df_raw = cargar_raw()
    df_limpio = limpiar(df_raw)
    reporte_calidad(df_limpio)
    guardar(df_limpio)


if __name__ == "__main__":
    main()