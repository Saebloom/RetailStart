# ============================================================
#  RetailStart Chile S.A. — Data Platform
#  Archivo : scripts/quality/validate.py
#  Etapa   : Calidad de datos — cleaned/ → cleaned/ (corregido)
# ============================================================
 
import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
 
load_dotenv()
 
# ------------------------------------------------------------
# Rutas base
# ------------------------------------------------------------
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLEANED     = os.path.join(BASE_DIR, "data", "processed", "cleaned")
TRANSFORMED = os.path.join(BASE_DIR, "data", "processed", "transformed")
 
 
def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
 
 
# ============================================================
#  REPORTE DE CALIDAD
# ============================================================
 
def reporte_calidad(df: pd.DataFrame, nombre: str):
    """Imprime un resumen de calidad del DataFrame."""
    duplicados = df.duplicated().sum()
    nulos      = df.isnull().sum().sum()
 
    _log(f"  [{nombre}]")
    _log(f"    Filas        : {len(df)}")
    _log(f"    Duplicados   : {duplicados}")
    _log(f"    Nulos totales: {nulos}")
 
    if nulos > 0:
        por_columna = df.isnull().sum()
        por_columna = por_columna[por_columna > 0]
        for col, cant in por_columna.items():
            _log(f"    ⚠ Nulos en '{col}': {cant}")
 
 
# ============================================================
#  LIMPIEZA por dataset
# ============================================================
 
def limpiar_ventas_pos(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates()
    df["fecha"]           = pd.to_datetime(df["fecha"])
    df["cantidad"]        = df["cantidad"].astype(int)
    df["precio_unitario"] = df["precio_unitario"].astype(float)
    df["total_venta"]     = df["cantidad"] * df["precio_unitario"]
    df["tienda"]          = df["tienda"].str.strip()
    df["fuente"]          = "POS"
    return df
 
 
def limpiar_ventas_online(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates()
    df["fecha"]       = pd.to_datetime(df["fecha"])
    df["total"]       = df["total"].astype(float)
    df["canal"]       = df["canal"].str.strip().str.lower()
    df["fuente"]      = "online"
    # Renombrar para unificar con ventas_pos
    df = df.rename(columns={"id_orden": "id_venta", "total": "total_venta"})
    return df
 
 
def limpiar_clientes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates(subset=["id_cliente"])
    # Eliminar duplicados por email (problema mencionado en informe 1)
    df = df.drop_duplicates(subset=["email"], keep="first")
    df["nombre"]   = df["nombre"].str.strip().str.title()
    df["apellido"] = df["apellido"].str.strip().str.title()
    df["email"]    = df["email"].str.strip().str.lower()
    df["segmento"] = df["segmento"].str.strip()
    df["ciudad"]   = df["ciudad"].str.strip()
    return df
 
 
def limpiar_productos(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates(subset=["id_producto"])
    df["nombre_producto"] = df["nombre_producto"].str.strip()
    df["categoria"]       = df["categoria"].str.strip()
    df["precio_base"]     = df["precio_base"].astype(float)
    df["proveedor"]       = df["proveedor"].str.strip()
    return df
 
 
def limpiar_logistica(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates()
    df["estado"] = df["estado"].str.strip()
    return df
 
 
def limpiar_eventos_app(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates()
    df["tipo"] = df["tipo"].str.strip().str.lower()
    return df
 
 
def limpiar_callcenter(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates()
    df["fecha"]   = pd.to_datetime(df["fecha"])
    df["motivo"]  = df["motivo"].str.strip()
    df["duracion"] = df["duracion"].astype(int)
    return df
 
 
def limpiar_redes_sociales(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates()
    df["comentario"] = df["comentario"].str.strip()
    df["rating"]     = df["rating"].astype(int)
    return df
 
 
def limpiar_generica(df: pd.DataFrame) -> pd.DataFrame:
    """Limpieza básica para datasets sin reglas específicas."""
    df = df.drop_duplicates()
    return df
 
 
# ============================================================
#  GUARDAR dataset limpio
# ============================================================
 
def guardar_limpio(df: pd.DataFrame, nombre: str):
    os.makedirs(TRANSFORMED, exist_ok=True)
    ruta = os.path.join(TRANSFORMED, nombre)
    df.to_csv(ruta, index=False)
    _log(f"  Guardado: {nombre} ({len(df)} filas)")
 
 
# ============================================================
#  FUNCIÓN PRINCIPAL
# ============================================================
 
def run() -> dict:
    _log("=" * 50)
    _log("INICIO VALIDACIÓN Y LIMPIEZA DE DATOS")
    _log("=" * 50)
 
    datasets_limpios = {}
 
    # ----------------------------------------------------------
    # Cargar desde cleaned/ (raw)
    # ----------------------------------------------------------
    def cargar(nombre):
        ruta = os.path.join(CLEANED, f"{nombre}_raw.csv")
        return pd.read_csv(ruta)
 
    # ----------------------------------------------------------
    # Validar calidad ANTES de limpiar
    # ----------------------------------------------------------
    _log("")
    _log(">> REPORTE DE CALIDAD INICIAL:")
    _log("-" * 40)
    archivos = [
        "ventas_pos", "ventas_online", "clientes_crm", "productos_erp",
        "logistica", "eventos_app", "callcenter", "redes_sociales",
        "proveedores", "multimedia", "logs_sistema"
    ]
    for a in archivos:
        reporte_calidad(cargar(a), a)
 
    # ----------------------------------------------------------
    # Limpiar cada dataset
    # ----------------------------------------------------------
    _log("")
    _log(">> LIMPIEZA:")
    _log("-" * 40)
 
    datasets_limpios["ventas_pos"]    = limpiar_ventas_pos(cargar("ventas_pos"))
    guardar_limpio(datasets_limpios["ventas_pos"], "ventas_pos_clean.csv")
 
    datasets_limpios["ventas_online"] = limpiar_ventas_online(cargar("ventas_online"))
    guardar_limpio(datasets_limpios["ventas_online"], "ventas_online_clean.csv")
 
    datasets_limpios["clientes_crm"]  = limpiar_clientes(cargar("clientes_crm"))
    guardar_limpio(datasets_limpios["clientes_crm"], "clientes_crm_clean.csv")
 
    datasets_limpios["productos_erp"] = limpiar_productos(cargar("productos_erp"))
    guardar_limpio(datasets_limpios["productos_erp"], "productos_erp_clean.csv")
 
    datasets_limpios["logistica"]     = limpiar_logistica(cargar("logistica"))
    guardar_limpio(datasets_limpios["logistica"], "logistica_clean.csv")
 
    datasets_limpios["eventos_app"]   = limpiar_eventos_app(cargar("eventos_app"))
    guardar_limpio(datasets_limpios["eventos_app"], "eventos_app_clean.csv")
 
    datasets_limpios["callcenter"]    = limpiar_callcenter(cargar("callcenter"))
    guardar_limpio(datasets_limpios["callcenter"], "callcenter_clean.csv")
 
    datasets_limpios["redes_sociales"] = limpiar_redes_sociales(cargar("redes_sociales"))
    guardar_limpio(datasets_limpios["redes_sociales"], "redes_sociales_clean.csv")
 
    datasets_limpios["proveedores"]   = limpiar_generica(cargar("proveedores"))
    guardar_limpio(datasets_limpios["proveedores"], "proveedores_clean.csv")
 
    datasets_limpios["multimedia"]    = limpiar_generica(cargar("multimedia"))
    guardar_limpio(datasets_limpios["multimedia"], "multimedia_clean.csv")
 
    datasets_limpios["logs_sistema"]  = limpiar_generica(cargar("logs_sistema"))
    guardar_limpio(datasets_limpios["logs_sistema"], "logs_sistema_clean.csv")
 
    _log("")
    _log("=" * 50)
    _log(f"VALIDACIÓN COMPLETA — {len(datasets_limpios)} datasets limpios")
    _log("=" * 50)
 
    return datasets_limpios
 
 
# ============================================================
#  Ejecución directa
# ============================================================
if __name__ == "__main__":
    run()