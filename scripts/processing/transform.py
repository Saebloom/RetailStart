# ============================================================
#  RetailStart Chile S.A. — Data Platform
#  Archivo : scripts/processing/transform.py
#  Versión : 3.0 — con soporte de fecha como argumento
#  Uso     : python transform.py [fecha]
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


def cargar(nombre: str, transformed_dir: str) -> pd.DataFrame | None:
    ruta = os.path.join(transformed_dir, f"{nombre}_clean.csv")
    if not os.path.isfile(ruta):
        return None
    return pd.read_csv(ruta)


def guardar(df: pd.DataFrame, nombre: str, integrated_dir: str):
    ruta = os.path.join(integrated_dir, nombre)
    df.to_csv(ruta, index=False)
    _log(f"  Guardado: {nombre} ({len(df)} filas)")


# ── Consolidación ────────────────────────────────────────────

def consolidar_ventas(transformed_dir: str) -> pd.DataFrame | None:
    pos    = cargar("ventas_pos",    transformed_dir)
    online = cargar("ventas_online", transformed_dir)

    if pos is None and online is None:
        _log("  Sin datos de ventas — omitiendo")
        return None

    partes = []

    if pos is not None:
        std = pos[["id_venta", "fecha", "id_cliente", "id_producto",
                   "cantidad", "precio_unitario", "total_venta", "fuente"]].copy()
        std["canal"]  = "tienda_fisica"
        std["tienda"] = pos["tienda"]
        partes.append(std)
        _log(f"  ventas_pos: {len(pos)} registros")

    if online is not None:
        std = online[["id_venta", "fecha", "id_cliente",
                      "total_venta", "canal", "fuente"]].copy()
        std["id_producto"]     = None
        std["cantidad"]        = 1
        std["precio_unitario"] = std["total_venta"]
        std["tienda"]          = None
        partes.append(std)
        _log(f"  ventas_online: {len(online)} registros")

    ventas = pd.concat(partes, ignore_index=True)
    ventas["fecha"] = pd.to_datetime(ventas["fecha"])
    return ventas.sort_values("fecha").reset_index(drop=True)


def enriquecer(ventas: pd.DataFrame, transformed_dir: str) -> pd.DataFrame:
    clientes  = cargar("clientes_crm",  transformed_dir)
    productos = cargar("productos_erp", transformed_dir)

    if clientes is not None:
        ventas = ventas.merge(
            clientes[["id_cliente", "nombre", "apellido", "segmento", "ciudad"]],
            on="id_cliente", how="left"
        )
        _log("  Enriquecido con clientes")

    if productos is not None:
        ventas = ventas.merge(
            productos[["id_producto", "nombre_producto", "categoria"]],
            on="id_producto", how="left"
        )
        _log("  Enriquecido con productos")

    return ventas


# ── Métricas ─────────────────────────────────────────────────

def metrica_clientes(ventas: pd.DataFrame) -> pd.DataFrame | None:
    extra = [c for c in ["nombre", "apellido", "segmento", "ciudad"] if c in ventas.columns]
    gcols = ["id_cliente"] + extra
    return ventas.groupby(gcols, as_index=False).agg(
        total_compras   = ("total_venta", "sum"),
        num_transacc    = ("id_venta",    "count"),
        ticket_promedio = ("total_venta", "mean")
    ).sort_values("total_compras", ascending=False)


def metrica_canal(ventas: pd.DataFrame) -> pd.DataFrame | None:
    if "canal" not in ventas.columns:
        return None
    df = ventas.groupby("canal", as_index=False).agg(
        total_ventas  = ("total_venta", "sum"),
        transacciones = ("id_venta",    "count")
    )
    df["porcentaje"] = (df["total_ventas"] / df["total_ventas"].sum() * 100).round(1)
    return df.sort_values("total_ventas", ascending=False)


def metrica_producto(ventas: pd.DataFrame) -> pd.DataFrame | None:
    if "nombre_producto" not in ventas.columns:
        return None
    return ventas.dropna(subset=["id_producto"]).groupby(
        ["id_producto", "nombre_producto", "categoria"], as_index=False
    ).agg(
        total_ventas = ("total_venta", "sum"),
        unidades     = ("cantidad",    "sum")
    ).sort_values("total_ventas", ascending=False)


def metrica_categoria(ventas: pd.DataFrame) -> pd.DataFrame | None:
    if "categoria" not in ventas.columns:
        return None
    return ventas.dropna(subset=["categoria"]).groupby(
        "categoria", as_index=False
    ).agg(
        total_ventas  = ("total_venta", "sum"),
        transacciones = ("id_venta",    "count")
    ).sort_values("total_ventas", ascending=False)


def metrica_fecha(ventas: pd.DataFrame) -> pd.DataFrame | None:
    if "fecha" not in ventas.columns:
        return None
    return ventas.groupby("fecha", as_index=False).agg(
        total_ventas  = ("total_venta", "sum"),
        transacciones = ("id_venta",    "count")
    ).sort_values("fecha")


def run(fecha: str = None):
    if fecha is None:
        fecha = sys.argv[1] if len(sys.argv) > 1 else "sin_fecha"

    transformed_dir = get_dir("transformed", fecha)
    integrated_dir  = get_dir("integrated",  fecha)

    _log("=" * 50)
    _log(f"INICIO PROCESAMIENTO — Fecha: {fecha}")
    _log("=" * 50)

    resultados = {}

    # Consolidar ventas del día
    _log("\n>> Consolidando ventas...")
    ventas = consolidar_ventas(transformed_dir)

    if ventas is None:
        _log("Sin ventas — procesamiento omitido")
        return resultados

    guardar(ventas, "ventas_consolidadas.csv", integrated_dir)
    resultados["ventas_consolidadas"] = ventas

    # Enriquecer
    _log("\n>> Enriqueciendo...")
    ventas_enriq = enriquecer(ventas, transformed_dir)
    guardar(ventas_enriq, "ventas_enriquecidas.csv", integrated_dir)
    resultados["ventas_enriquecidas"] = ventas_enriq

    # Métricas del día
    _log("\n>> Generando metricas del dia:")
    metricas = {
        "metricas_clientes":  metrica_clientes(ventas_enriq),
        "metricas_canal":     metrica_canal(ventas_enriq),
        "metricas_producto":  metrica_producto(ventas_enriq),
        "metricas_categoria": metrica_categoria(ventas_enriq),
        "metricas_fecha":     metrica_fecha(ventas_enriq),
    }

    for nombre, df in metricas.items():
        if df is not None and len(df) > 0:
            guardar(df, f"{nombre}.csv", integrated_dir)
            resultados[nombre] = df
        else:
            _log(f"  Omitida: {nombre} (datos insuficientes)")

    # Preview
    if "metricas_canal" in resultados:
        _log("\n>> Ventas por canal:")
        for _, row in resultados["metricas_canal"].iterrows():
            _log(f"   {row['canal']} — ${row['total_ventas']:,.0f} ({row['porcentaje']}%)")

    _log("")
    _log("=" * 50)
    _log(f"PROCESAMIENTO COMPLETO — {len(resultados)} datasets | Fecha: {fecha}")
    _log("=" * 50)
    return resultados


if __name__ == "__main__":
    run()