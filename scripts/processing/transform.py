# ============================================================
#  RetailStart Chile S.A. — Data Platform
#  Archivo : scripts/processing/transform.py
#  Etapa   : Procesamiento — transformed/ → integrated/
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
TRANSFORMED = os.path.join(BASE_DIR, "data", "processed", "transformed")
INTEGRATED  = os.path.join(BASE_DIR, "data", "processed", "integrated")
 
 
def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
 
 
def cargar(nombre: str) -> pd.DataFrame:
    ruta = os.path.join(TRANSFORMED, f"{nombre}_clean.csv")
    return pd.read_csv(ruta)
 
 
def guardar(df: pd.DataFrame, nombre: str):
    os.makedirs(INTEGRATED, exist_ok=True)
    ruta = os.path.join(INTEGRATED, nombre)
    df.to_csv(ruta, index=False)
    _log(f"  Guardado: {nombre} ({len(df)} filas)")
 
 
# ============================================================
#  PASO 1 — Consolidar ventas POS + online en un solo dataset
# ============================================================
 
def consolidar_ventas() -> pd.DataFrame:
    _log(">> Consolidando ventas POS + online...")
 
    pos    = cargar("ventas_pos")
    online = cargar("ventas_online")
 
    # Columnas comunes para unificar
    pos_std = pos[[
        "id_venta", "fecha", "id_cliente", "id_producto",
        "cantidad", "precio_unitario", "total_venta", "fuente"
    ]].copy()
    pos_std["canal"]  = "tienda_fisica"
    pos_std["tienda"] = pos["tienda"]
 
    online_std = online[[
        "id_venta", "fecha", "id_cliente",
        "total_venta", "canal", "fuente"
    ]].copy()
    online_std["id_producto"]    = None
    online_std["cantidad"]       = 1
    online_std["precio_unitario"] = online_std["total_venta"]
    online_std["tienda"]         = None
 
    ventas = pd.concat([pos_std, online_std], ignore_index=True)
    ventas["fecha"] = pd.to_datetime(ventas["fecha"])
    ventas = ventas.sort_values("fecha").reset_index(drop=True)
 
    _log(f"  Total ventas consolidadas: {len(ventas)}")
    return ventas
 
 
# ============================================================
#  PASO 2 — Enriquecer ventas con clientes y productos
# ============================================================
 
def enriquecer_ventas(ventas: pd.DataFrame) -> pd.DataFrame:
    _log(">> Enriqueciendo ventas con clientes y productos...")
 
    clientes  = cargar("clientes_crm")
    productos = cargar("productos_erp")
 
    # Unir con clientes
    ventas = ventas.merge(
        clientes[["id_cliente", "nombre", "apellido", "segmento", "ciudad"]],
        on="id_cliente",
        how="left"
    )
 
    # Unir con productos (solo ventas POS tienen id_producto)
    ventas = ventas.merge(
        productos[["id_producto", "nombre_producto", "categoria"]],
        on="id_producto",
        how="left"
    )
 
    _log(f"  Ventas enriquecidas: {len(ventas)} filas")
    return ventas
 
 
# ============================================================
#  PASO 3 — Generar métricas analíticas
# ============================================================
 
def ventas_por_cliente(ventas: pd.DataFrame) -> pd.DataFrame:
    _log(">> Calculando ventas por cliente...")
 
    df = ventas.groupby(
        ["id_cliente", "nombre", "apellido", "segmento", "ciudad"],
        as_index=False
    ).agg(
        total_compras   = ("total_venta", "sum"),
        num_transacc    = ("id_venta",    "count"),
        ticket_promedio = ("total_venta", "mean")
    ).sort_values("total_compras", ascending=False)
 
    df["ticket_promedio"] = df["ticket_promedio"].round(0)
    return df
 
 
def ventas_por_canal(ventas: pd.DataFrame) -> pd.DataFrame:
    _log(">> Calculando ventas por canal...")
 
    df = ventas.groupby("canal", as_index=False).agg(
        total_ventas  = ("total_venta", "sum"),
        transacciones = ("id_venta",    "count")
    ).sort_values("total_ventas", ascending=False)
 
    df["porcentaje"] = (df["total_ventas"] / df["total_ventas"].sum() * 100).round(1)
    return df
 
 
def ventas_por_producto(ventas: pd.DataFrame) -> pd.DataFrame:
    _log(">> Calculando ventas por producto...")
 
    df = ventas.dropna(subset=["id_producto"]).groupby(
        ["id_producto", "nombre_producto", "categoria"],
        as_index=False
    ).agg(
        total_ventas = ("total_venta", "sum"),
        unidades     = ("cantidad",    "sum")
    ).sort_values("total_ventas", ascending=False)
 
    return df
 
 
def ventas_por_categoria(ventas: pd.DataFrame) -> pd.DataFrame:
    _log(">> Calculando ventas por categoría...")
 
    df = ventas.dropna(subset=["categoria"]).groupby(
        "categoria", as_index=False
    ).agg(
        total_ventas = ("total_venta", "sum"),
        transacciones = ("id_venta",   "count")
    ).sort_values("total_ventas", ascending=False)
 
    return df
 
 
def ventas_por_fecha(ventas: pd.DataFrame) -> pd.DataFrame:
    _log(">> Calculando ventas por fecha...")
 
    df = ventas.groupby("fecha", as_index=False).agg(
        total_ventas  = ("total_venta", "sum"),
        transacciones = ("id_venta",    "count")
    ).sort_values("fecha")
 
    return df
 
 
# ============================================================
#  FUNCIÓN PRINCIPAL
# ============================================================
 
def run() -> dict:
    _log("=" * 50)
    _log("INICIO PROCESAMIENTO DE DATOS")
    _log("=" * 50)
 
    resultados = {}
 
    # Paso 1 — Consolidar
    ventas = consolidar_ventas()
    guardar(ventas, "ventas_consolidadas.csv")
    resultados["ventas_consolidadas"] = ventas
 
    # Paso 2 — Enriquecer
    ventas_enriq = enriquecer_ventas(ventas)
    guardar(ventas_enriq, "ventas_enriquecidas.csv")
    resultados["ventas_enriquecidas"] = ventas_enriq
 
    # Paso 3 — Métricas
    _log("")
    _log(">> GENERANDO MÉTRICAS:")
    _log("-" * 40)
 
    df_clientes = ventas_por_cliente(ventas_enriq)
    guardar(df_clientes, "metricas_clientes.csv")
    resultados["metricas_clientes"] = df_clientes
 
    df_canal = ventas_por_canal(ventas_enriq)
    guardar(df_canal, "metricas_canal.csv")
    resultados["metricas_canal"] = df_canal
 
    df_producto = ventas_por_producto(ventas_enriq)
    guardar(df_producto, "metricas_producto.csv")
    resultados["metricas_producto"] = df_producto
 
    df_categoria = ventas_por_categoria(ventas_enriq)
    guardar(df_categoria, "metricas_categoria.csv")
    resultados["metricas_categoria"] = df_categoria
 
    df_fecha = ventas_por_fecha(ventas_enriq)
    guardar(df_fecha, "metricas_fecha.csv")
    resultados["metricas_fecha"] = df_fecha
 
    # Preview de resultados clave
    _log("")
    _log(">> RESUMEN DE RESULTADOS:")
    _log("-" * 40)
    _log("Top 3 clientes por volumen de compra:")
    for _, row in df_clientes.head(3).iterrows():
        _log(f"  {row['nombre']} {row['apellido']} — ${row['total_compras']:,.0f} ({row['num_transacc']} transacciones)")
 
    _log("")
    _log("Ventas por canal:")
    for _, row in df_canal.iterrows():
        _log(f"  {row['canal']} — ${row['total_ventas']:,.0f} ({row['porcentaje']}%)")
 
    _log("")
    _log("Top 3 productos más vendidos:")
    for _, row in df_producto.head(3).iterrows():
        _log(f"  {row['nombre_producto']} — ${row['total_ventas']:,.0f}")
 
    _log("")
    _log("=" * 50)
    _log(f"PROCESAMIENTO COMPLETO — {len(resultados)} datasets generados")
    _log("=" * 50)
 
    return resultados
 
 
# ============================================================
#  Ejecución directa
# ============================================================
if __name__ == "__main__":
    run()