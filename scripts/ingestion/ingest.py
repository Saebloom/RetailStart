import os
import pandas as pd
from lxml import etree
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_CSV  = os.path.join(BASE_DIR, "data", "raw", "csv")
RAW_JSON = os.path.join(BASE_DIR, "data", "raw", "json")
RAW_XML  = os.path.join(BASE_DIR, "data", "raw", "xml")
RAW_TXT  = os.path.join(BASE_DIR, "data", "raw", "txt")
CLEANED  = os.path.join(BASE_DIR, "data", "processed", "cleaned")

# Catálogo de todos los archivos conocidos por el sistema
CATALOGO = {
    "csv":  ["ventas_pos.csv", "clientes_crm.csv", "productos_erp.csv",
             "ventas_online.csv", "callcenter.csv", "proveedores.csv", "multimedia.csv"],
    "json": ["eventos_app.json", "redes_sociales.json"],
    "xml":  ["logistica.xml"],
    "txt":  ["logs_sistema.txt"],
}


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def existe(carpeta: str, nombre: str) -> bool:
    """Verifica si un archivo existe antes de intentar leerlo."""
    return os.path.isfile(os.path.join(carpeta, nombre))


def leer_csv(nombre: str) -> pd.DataFrame | None:
    if not existe(RAW_CSV, nombre):
        _log(f"  Omitido (no encontrado): {nombre}")
        return None
    ruta = os.path.join(RAW_CSV, nombre)
    df = pd.read_csv(ruta)
    _log(f"  CSV cargado: {nombre} — {len(df)} filas, {len(df.columns)} columnas")
    return df


def leer_json(nombre: str) -> pd.DataFrame | None:
    if not existe(RAW_JSON, nombre):
        _log(f"  Omitido (no encontrado): {nombre}")
        return None
    ruta = os.path.join(RAW_JSON, nombre)
    df = pd.read_json(ruta)
    _log(f"  JSON cargado: {nombre} — {len(df)} filas, {len(df.columns)} columnas")
    return df


def leer_xml(nombre: str) -> pd.DataFrame | None:
    if not existe(RAW_XML, nombre):
        _log(f"  Omitido (no encontrado): {nombre}")
        return None
    ruta = os.path.join(RAW_XML, nombre)
    tree = etree.parse(ruta)
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
        _log(f"  Omitido (no encontrado): {nombre}")
        return None
    ruta = os.path.join(RAW_TXT, nombre)
    registros = []
    with open(ruta, "r", encoding="utf-8") as f:
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


def guardar_cleaned(df: pd.DataFrame, nombre: str):
    os.makedirs(CLEANED, exist_ok=True)
    ruta = os.path.join(CLEANED, nombre)
    df.to_csv(ruta, index=False)
    _log(f"  Guardado en cleaned: {nombre}")


def run() -> dict:
    _log("=" * 50)
    _log("INICIO INGESTA DE DATOS")
    _log("=" * 50)

    datasets = {}

    _log("")
    _log(">> Archivos CSV:")
    for nombre in CATALOGO["csv"]:
        clave = nombre.replace(".csv", "")
        df = leer_csv(nombre)
        if df is not None:
            datasets[clave] = df

    _log("")
    _log(">> Archivos JSON:")
    for nombre in CATALOGO["json"]:
        clave = nombre.replace(".json", "")
        df = leer_json(nombre)
        if df is not None:
            datasets[clave] = df

    _log("")
    _log(">> Archivos XML:")
    for nombre in CATALOGO["xml"]:
        clave = nombre.replace(".xml", "")
        df = leer_xml(nombre)
        if df is not None:
            datasets[clave] = df

    _log("")
    _log(">> Archivos TXT:")
    for nombre in CATALOGO["txt"]:
        clave = nombre.replace(".txt", "")
        df = leer_txt(nombre)
        if df is not None:
            datasets[clave] = df

    _log("")
    _log(">> Guardando en cleaned/:")
    for nombre, df in datasets.items():
        guardar_cleaned(df, f"{nombre}_raw.csv")

    _log("")
    _log("=" * 50)
    _log(f"INGESTA COMPLETA — {len(datasets)} fuentes cargadas")
    _log("=" * 50)

    return datasets


if __name__ == "__main__":
    run()