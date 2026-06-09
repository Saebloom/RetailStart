import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(encoding="utf-8")

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLEANED     = os.path.join(BASE_DIR, "data", "processed", "cleaned")
TRANSFORMED = os.path.join(BASE_DIR, "data", "processed", "transformed")


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def existe_cleaned(nombre: str) -> bool:
    return os.path.isfile(os.path.join(CLEANED, f"{nombre}_raw.csv"))


def cargar(nombre: str) -> pd.DataFrame | None:
    ruta = os.path.join(CLEANED, f"{nombre}_raw.csv")
    if not os.path.isfile(ruta):
        return None
    return pd.read_csv(ruta)


def guardar_limpio(df: pd.DataFrame, nombre: str):
    os.makedirs(TRANSFORMED, exist_ok=True)
    ruta = os.path.join(TRANSFORMED, nombre)
    df.to_csv(ruta, index=False)
    _log(f"  Guardado: {nombre} ({len(df)} filas)")


def reporte_calidad(df: pd.DataFrame, nombre: str):
    duplicados = df.duplicated().sum()
    nulos      = df.isnull().sum().sum()
    _log(f"  [{nombre}] Filas: {len(df)}  Duplicados: {duplicados}  Nulos: {nulos}")
    if nulos > 0:
        por_col = df.isnull().sum()
        for col, cant in por_col[por_col > 0].items():
            _log(f"    Nulos en '{col}': {cant}")


# ── Funciones de limpieza específicas ───────────────────────

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
    df["fecha"]       = pd.to_datetime(df["fecha"])
    df["total"]       = df["total"].astype(float)
    df["canal"]       = df["canal"].str.strip().str.lower()
    df["fuente"]      = "online"
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
    df["fecha"]    = pd.to_datetime(df["fecha"])
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


# Mapeo nombre → función de limpieza
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


def run() -> dict:
    _log("=" * 50)
    _log("INICIO VALIDACIÓN Y LIMPIEZA DE DATOS")
    _log("=" * 50)

    # Detectar qué datasets están disponibles en cleaned/
    disponibles = [n for n in LIMPIEZAS.keys() if existe_cleaned(n)]

    if not disponibles:
        _log("No se encontraron archivos en cleaned/ — ejecuta ingest.py primero")
        return {}

    _log("")
    _log(f">> Datasets disponibles: {len(disponibles)}")

    # Reporte de calidad
    _log("")
    _log(">> REPORTE DE CALIDAD INICIAL:")
    _log("-" * 40)
    for nombre in disponibles:
        df = cargar(nombre)
        if df is not None:
            reporte_calidad(df, nombre)

    # Limpieza
    _log("")
    _log(">> LIMPIEZA:")
    _log("-" * 40)

    datasets_limpios = {}
    for nombre in disponibles:
        df = cargar(nombre)
        if df is None:
            continue
        fn_limpiar = LIMPIEZAS[nombre]
        df_limpio  = fn_limpiar(df)
        guardar_limpio(df_limpio, f"{nombre}_clean.csv")
        datasets_limpios[nombre] = df_limpio

    _log("")
    _log("=" * 50)
    _log(f"VALIDACIÓN COMPLETA — {len(datasets_limpios)} datasets limpios")
    _log("=" * 50)

    return datasets_limpios


if __name__ == "__main__":
    run()