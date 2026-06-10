# ============================================================
#  RetailStart Chile S.A. — Data Platform
#  Archivo : scripts/ingestion/ingest.py
#  Versión : 3.0 — con soporte de fecha como argumento
#  Uso     : python ingest.py [fecha]
#            fecha formato YYYY-MM-DD o "maestros"
# ============================================================

import os
import sys
import pandas as pd
from lxml import etree
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(encoding="utf-8")

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_CSV     = os.path.join(BASE_DIR, "data", "raw", "csv")
RAW_JSON    = os.path.join(BASE_DIR, "data", "raw", "json")
RAW_XML     = os.path.join(BASE_DIR, "data", "raw", "xml")
RAW_TXT     = os.path.join(BASE_DIR, "data", "raw", "txt")

CATALOGO = {
    "csv":  ["ventas_pos.csv", "clientes_crm.csv", "productos_erp.csv",
             "ventas_online.csv", "callcenter.csv", "proveedores.csv", "multimedia.csv"],
    "json": ["eventos_app.json", "redes_sociales.json"],
    "xml":  ["logistica.xml"],
    "txt":  ["logs_sistema.txt"],
}


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def get_cleaned_dir(fecha: str) -> str:
    """Retorna la carpeta cleaned correspondiente a la fecha."""
    ruta = os.path.join(BASE_DIR, "data", "processed", "cleaned", fecha)
    os.makedirs(ruta, exist_ok=True)
    return ruta


def existe(carpeta: str, nombre: str) -> bool:
    return os.path.isfile(os.path.join(carpeta, nombre))


def leer_csv(nombre: str) -> pd.DataFrame | None:
    if not existe(RAW_CSV, nombre):
        return None
    df = pd.read_csv(os.path.join(RAW_CSV, nombre))
    _log(f"  CSV cargado: {nombre} — {len(df)} filas")
    return df


def leer_json(nombre: str) -> pd.DataFrame | None:
    if not existe(RAW_JSON, nombre):
        return None
    df = pd.read_json(os.path.join(RAW_JSON, nombre))
    _log(f"  JSON cargado: {nombre} — {len(df)} filas")
    return df


def leer_xml(nombre: str) -> pd.DataFrame | None:
    if not existe(RAW_XML, nombre):
        return None
    tree = etree.parse(os.path.join(RAW_XML, nombre))
    root = tree.getroot()
    registros = []
    for pedido in root.findall("pedido"):
        registros.append({
            "id_pedido":  int(pedido.find("id").text),
            "id_cliente": int(pedido.find("cliente").text),
            "estado":     pedido.find("estado").text.strip()
        })
    df = pd.DataFrame(registros)
    _log(f"  XML cargado: {nombre} — {len(df)} filas")
    return df


def leer_txt(nombre: str) -> pd.DataFrame | None:
    if not existe(RAW_TXT, nombre):
        return None
    registros = []
    with open(os.path.join(RAW_TXT, nombre), "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            partes = linea.split(" ", 3)
            registros.append({
                "fecha":   partes[0] if len(partes) > 0 else None,
                "hora":    partes[1] if len(partes) > 1 else None,
                "accion":  partes[2] if len(partes) > 2 else None,
                "detalle": partes[3] if len(partes) > 3 else None
            })
    df = pd.DataFrame(registros)
    _log(f"  TXT cargado: {nombre} — {len(df)} filas")
    return df


def guardar(df: pd.DataFrame, nombre: str, cleaned_dir: str):
    ruta = os.path.join(cleaned_dir, nombre)
    df.to_csv(ruta, index=False)
    _log(f"  Guardado: {nombre} ({len(df)} filas)")


def run(fecha: str = None):
    if fecha is None:
        fecha = sys.argv[1] if len(sys.argv) > 1 else "sin_fecha"

    cleaned_dir = get_cleaned_dir(fecha)

    _log("=" * 50)
    _log(f"INICIO INGESTA — Fecha: {fecha}")
    _log("=" * 50)

    datasets = {}

    # CSV — leer desde raw/ y filtrar por fecha si aplica
    _log("\n>> Archivos CSV:")
    for nombre in CATALOGO["csv"]:
        clave = nombre.replace(".csv", "")
        # Intentar leer desde cleaned/FECHA/ (ya segmentado por watcher)
        ruta_segmentada = os.path.join(cleaned_dir, nombre.replace(".csv", "_raw.csv"))
        if os.path.isfile(ruta_segmentada):
            df = pd.read_csv(ruta_segmentada)
            _log(f"  CSV desde cleaned/{fecha}/: {nombre} — {len(df)} filas")
            datasets[clave] = df
        else:
            # Si no hay segmentado, leer desde raw/ completo
            df = leer_csv(nombre)
            if df is not None:
                # Filtrar por fecha si tiene columna fecha
                if "fecha" in df.columns and fecha not in ("maestros", "sin_fecha"):
                    df = df[pd.to_datetime(df["fecha"]).dt.strftime("%Y-%m-%d") == fecha]
                    _log(f"    Filtrado por fecha {fecha}: {len(df)} filas")
                if len(df) > 0:
                    guardar(df, f"{clave}_raw.csv", cleaned_dir)
                    datasets[clave] = df

    # JSON
    _log("\n>> Archivos JSON:")
    for nombre in CATALOGO["json"]:
        clave = nombre.replace(".json", "")
        df = leer_json(nombre)
        if df is not None:
            guardar(df, f"{clave}_raw.csv", cleaned_dir)
            datasets[clave] = df

    # XML
    _log("\n>> Archivos XML:")
    for nombre in CATALOGO["xml"]:
        clave = nombre.replace(".xml", "")
        df = leer_xml(nombre)
        if df is not None:
            guardar(df, f"{clave}_raw.csv", cleaned_dir)
            datasets[clave] = df

    # TXT
    _log("\n>> Archivos TXT:")
    for nombre in CATALOGO["txt"]:
        clave = nombre.replace(".txt", "")
        df = leer_txt(nombre)
        if df is not None:
            guardar(df, f"{clave}_raw.csv", cleaned_dir)
            datasets[clave] = df

    _log("")
    _log("=" * 50)
    _log(f"INGESTA COMPLETA — {len(datasets)} fuentes | Fecha: {fecha}")
    _log("=" * 50)
    return datasets


if __name__ == "__main__":
    run()