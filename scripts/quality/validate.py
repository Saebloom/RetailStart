# ============================================================
#  RetailStart Chile S.A. — Data Platform
#  Archivo : scripts/quality/validate.py
#  Versión : 3.0 — con soporte de fecha como argumento
#  Uso     : python validate.py [fecha]
# ============================================================

import os
import sys
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def get_dir(zona: str, fecha: str) -> str:
    ruta = os.path.join(BASE_DIR, "data", "processed", zona, fecha)
    os.makedirs(ruta, exist_ok=True)
    return ruta


def cargar(nombre: str, cleaned_dir: str) -> pd.DataFrame | None:
    ruta = os.path.join(cleaned_dir, f"{nombre}_raw.csv")
    if not os.path.isfile(ruta):
        return None
    return pd.read_csv(ruta)


def guardar(df: pd.DataFrame, nombre: str, transformed_dir: str):
    ruta = os.path.join(transformed_dir, nombre)
    df.to_csv(ruta, index=False)
    _log(f"  Guardado: {nombre} ({len(df)} filas)")


def reporte(df: pd.DataFrame, nombre: str):
    dups  = df.duplicated().sum()
    nulos = df.isnull().sum().sum()
    _log(f"  [{nombre}] Filas: {len(df)}  Dups: {dups}  Nulos: {nulos}")


# ── Funciones de limpieza ────────────────────────────────────

def limpiar_ventas_pos(df):
    df = df.drop_duplicates()
    df["fecha"]           = pd.to_datetime(df["fecha"])
    df["cantidad"]        = df["cantidad"].astype(int)
    df["precio_unitario"] = df["precio_unitario"].astype(float)
    df["total_venta"]     = df["cantidad"] * df["precio_unitario"]
    df["tienda"]          = df["tienda"].str.strip()
    df["fuente"]          = "POS"
    return df

def limpiar_ventas_online(df):
    df = df.drop_duplicates()
    df["fecha"]      = pd.to_datetime(df["fecha"])
    df["total"]      = df["total"].astype(float)
    df["canal"]      = df["canal"].str.strip().str.lower()
    df["fuente"]     = "online"
    df = df.rename(columns={"id_orden": "id_venta", "total": "total_venta"})
    return df

def limpiar_clientes(df):
    df = df.drop_duplicates(subset=["id_cliente"])
    df = df.drop_duplicates(subset=["email"], keep="first")
    df["nombre"]   = df["nombre"].str.strip().str.title()
    df["apellido"] = df["apellido"].str.strip().str.title()
    df["email"]    = df["email"].str.strip().str.lower()
    df["segmento"] = df["segmento"].str.strip()
    df["ciudad"]   = df["ciudad"].str.strip()
    return df

def limpiar_productos(df):
    df = df.drop_duplicates(subset=["id_producto"])
    df["nombre_producto"] = df["nombre_producto"].str.strip()
    df["categoria"]       = df["categoria"].str.strip()
    df["precio_base"]     = df["precio_base"].astype(float)
    df["proveedor"]       = df["proveedor"].str.strip()
    return df

def limpiar_logistica(df):
    df = df.drop_duplicates()
    df["estado"] = df["estado"].str.strip()
    return df

def limpiar_eventos_app(df):
    df = df.drop_duplicates()
    df["tipo"] = df["tipo"].str.strip().str.lower()
    return df

def limpiar_callcenter(df):
    df = df.drop_duplicates()
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"])
    df["motivo"]   = df["motivo"].str.strip()
    df["duracion"] = df["duracion"].astype(int)
    return df

def limpiar_redes_sociales(df):
    df = df.drop_duplicates()
    df["comentario"] = df["comentario"].str.strip()
    df["rating"]     = df["rating"].astype(int)
    return df

def limpiar_generica(df):
    return df.drop_duplicates()


LIMPIEZAS = {
    "ventas_pos":    limpiar_ventas_pos,
    "ventas_online": limpiar_ventas_online,
    "clientes_crm":  limpiar_clientes,
    "productos_erp": limpiar_productos,
    "logistica":     limpiar_logistica,
    "eventos_app":   limpiar_eventos_app,
    "callcenter":    limpiar_callcenter,
    "redes_sociales":limpiar_redes_sociales,
    "proveedores":   limpiar_generica,
    "multimedia":    limpiar_generica,
    "logs_sistema":  limpiar_generica,
}


def run(fecha: str = None):
    if fecha is None:
        fecha = sys.argv[1] if len(sys.argv) > 1 else "sin_fecha"

    cleaned_dir     = get_dir("cleaned", fecha)
    transformed_dir = get_dir("transformed", fecha)

    _log("=" * 50)
    _log(f"INICIO VALIDACION — Fecha: {fecha}")
    _log("=" * 50)

    disponibles = [n for n in LIMPIEZAS if
                   os.path.isfile(os.path.join(cleaned_dir, f"{n}_raw.csv"))]

    if not disponibles:
        _log(f"Sin archivos en cleaned/{fecha}/ — omitiendo")
        return {}

    _log(f"\n>> Datasets disponibles ({len(disponibles)}): {disponibles}")

    _log("\n>> Reporte de calidad:")
    for nombre in disponibles:
        df = cargar(nombre, cleaned_dir)
        if df is not None:
            reporte(df, nombre)

    _log("\n>> Limpieza:")
    datasets_limpios = {}
    for nombre in disponibles:
        df = cargar(nombre, cleaned_dir)
        if df is None:
            continue
        df_limpio = LIMPIEZAS[nombre](df)
        guardar(df_limpio, f"{nombre}_clean.csv", transformed_dir)
        datasets_limpios[nombre] = df_limpio

    _log("")
    _log("=" * 50)
    _log(f"VALIDACION COMPLETA — {len(datasets_limpios)} datasets | Fecha: {fecha}")
    _log("=" * 50)
    return datasets_limpios


if __name__ == "__main__":
    run()