# ============================================================
#  RetailStart Chile S.A. — Data Platform
#  Archivo : scripts/ingestion/ingest.py
#  Etapa   : Ingesta — Origen → Data Lake (data/raw/ ya existe,
#             este script valida lectura y registra metadata)
# ============================================================
 
import os
import json
import pandas as pd
from lxml import etree
from datetime import datetime
from dotenv import load_dotenv
 
# Carga automática del .env (credenciales BD y configuración)
load_dotenv()
 
# ------------------------------------------------------------
# Rutas base
# ------------------------------------------------------------
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_CSV    = os.path.join(BASE_DIR, "data", "raw", "csv")
RAW_JSON   = os.path.join(BASE_DIR, "data", "raw", "json")
RAW_XML    = os.path.join(BASE_DIR, "data", "raw", "xml")
RAW_TXT    = os.path.join(BASE_DIR, "data", "raw", "txt")
CLEANED    = os.path.join(BASE_DIR, "data", "processed", "cleaned")
 
 
def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
 
 
# ============================================================
#  LECTORES por formato
# ============================================================
 
def leer_csv(nombre_archivo: str) -> pd.DataFrame:
    ruta = os.path.join(RAW_CSV, nombre_archivo)
    df = pd.read_csv(ruta)
    _log(f"CSV cargado: {nombre_archivo} — {len(df)} filas, {len(df.columns)} columnas")
    return df
 
 
def leer_json(nombre_archivo: str) -> pd.DataFrame:
    ruta = os.path.join(RAW_JSON, nombre_archivo)
    df = pd.read_json(ruta)
    _log(f"JSON cargado: {nombre_archivo} — {len(df)} filas, {len(df.columns)} columnas")
    return df
 
 
def leer_xml(nombre_archivo: str) -> pd.DataFrame:
    """Lee logistica.xml y retorna un DataFrame con id, cliente y estado."""
    ruta = os.path.join(RAW_XML, nombre_archivo)
    tree = etree.parse(ruta)
    root = tree.getroot()
 
    registros = []
    for pedido in root.findall("pedido"):
        registros.append({
            "id_pedido": int(pedido.find("id").text),
            "id_cliente": int(pedido.find("cliente").text),
            "estado": pedido.find("estado").text.strip()
        })
 
    df = pd.DataFrame(registros)
    _log(f"XML cargado: {nombre_archivo} — {len(df)} filas")
    return df
 
 
def leer_txt(nombre_archivo: str) -> pd.DataFrame:
    """Lee logs_sistema.txt y lo parsea en columnas: fecha, hora, accion, detalle."""
    ruta = os.path.join(RAW_TXT, nombre_archivo)
    registros = []
 
    with open(ruta, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            partes = linea.split(" ", 3)          # max 4 partes
            registros.append({
                "fecha":   partes[0] if len(partes) > 0 else None,
                "hora":    partes[1] if len(partes) > 1 else None,
                "accion":  partes[2] if len(partes) > 2 else None,
                "detalle": partes[3] if len(partes) > 3 else None
            })
 
    df = pd.DataFrame(registros)
    _log(f"TXT cargado: {nombre_archivo} — {len(df)} filas")
    return df
 
 
# ============================================================
#  GUARDAR en Data Lake (processed/cleaned/ como staging)
# ============================================================
 
def guardar_cleaned(df: pd.DataFrame, nombre: str):
    os.makedirs(CLEANED, exist_ok=True)
    ruta = os.path.join(CLEANED, nombre)
    df.to_csv(ruta, index=False)
    _log(f"Guardado en cleaned: {nombre}")
 
 
# ============================================================
#  FUNCIÓN PRINCIPAL
# ============================================================
 
def run() -> dict:
    """
    Ejecuta la ingesta completa de todos los datasets.
    Retorna un diccionario con todos los DataFrames cargados.
    """
    _log("=" * 50)
    _log("INICIO INGESTA DE DATOS")
    _log("=" * 50)
 
    datasets = {}
 
    # ----------------------------------------------------------
    # CSV obligatorios
    # ----------------------------------------------------------
    datasets["ventas_pos"]    = leer_csv("ventas_pos.csv")
    datasets["clientes_crm"]  = leer_csv("clientes_crm.csv")
    datasets["productos_erp"] = leer_csv("productos_erp.csv")
    datasets["ventas_online"] = leer_csv("ventas_online.csv")
 
    # ----------------------------------------------------------
    # CSV opcionales
    # ----------------------------------------------------------
    datasets["callcenter"]    = leer_csv("callcenter.csv")
    datasets["proveedores"]   = leer_csv("proveedores.csv")
    datasets["multimedia"]    = leer_csv("multimedia.csv")
 
    # ----------------------------------------------------------
    # JSON
    # ----------------------------------------------------------
    datasets["eventos_app"]      = leer_json("eventos_app.json")
    datasets["redes_sociales"]   = leer_json("redes_sociales.json")
 
    # ----------------------------------------------------------
    # XML
    # ----------------------------------------------------------
    datasets["logistica"]     = leer_xml("logistica.xml")
 
    # ----------------------------------------------------------
    # TXT
    # ----------------------------------------------------------
    datasets["logs_sistema"]  = leer_txt("logs_sistema.txt")
 
    # ----------------------------------------------------------
    # Guardar copias en cleaned/ (staging del Data Lake)
    # ----------------------------------------------------------
    for nombre, df in datasets.items():
        guardar_cleaned(df, f"{nombre}_raw.csv")
 
    _log("=" * 50)
    _log(f"INGESTA COMPLETA — {len(datasets)} fuentes cargadas")
    _log("=" * 50)
 
    return datasets
 
 
# ============================================================
#  Ejecución directa (para pruebas)
# ============================================================
if __name__ == "__main__":
    run()