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


def cargar(nombre: str, fecha_dir: str, maestros_dir: str) -> pd.DataFrame | None:
    """Busca primero en la carpeta de la fecha, luego en maestros/."""
    for carpeta in (fecha_dir, maestros_dir):
        ruta = os.path.join(carpeta, f"{nombre}_clean.csv")
        if os.path.isfile(ruta):
            return pd.read_csv(ruta)
    return None


def consolidar_ventas(fecha_dir: str) -> pd.DataFrame | None:
    pos    = cargar("ventas_pos",    fecha_dir, fecha_dir)
    online = cargar("ventas_online", fecha_dir, fecha_dir)

    if pos is None and online is None:
        return None

    partes = []
    if pos is not None:
        std = pos[["id_venta", "fecha", "id_cliente", "id_producto",
                   "cantidad", "precio_unitario", "total_venta", "fuente"]].copy()
        std["canal"]  = "tienda_fisica"
        std["tienda"] = pos["tienda"]
        partes.append(std)

    if online is not None:
        std = online[["id_venta", "fecha", "id_cliente",
                      "total_venta", "canal", "fuente"]].copy()
        std["id_producto"]     = None
        std["cantidad"]        = 1
        std["precio_unitario"] = std["total_venta"]
        std["tienda"]          = None
        partes.append(std)

    ventas = pd.concat(partes, ignore_index=True)
    ventas["fecha"] = pd.to_datetime(ventas["fecha"])
    ventas["id_producto"] = pd.to_numeric(ventas["id_producto"], errors="coerce")

    return ventas.sort_values("fecha").reset_index(drop=True)


def enriquecer(ventas: pd.DataFrame, fecha_dir: str, maestros_dir: str) -> pd.DataFrame:
    clientes  = cargar("clientes_crm",  fecha_dir, maestros_dir)
    productos = cargar("productos_erp", fecha_dir, maestros_dir)

    if clientes is not None:
        ventas = ventas.merge(
            clientes[["id_cliente", "nombre", "apellido", "segmento", "ciudad"]],
            on="id_cliente", how="left"
        )

    if productos is not None:
        ventas = ventas.merge(
            productos[["id_producto", "nombre_producto", "categoria"]],
            on="id_producto", how="left"
        )

    return ventas

def metrica_clientes(v):
    extra = [c for c in ["nombre", "apellido", "segmento", "ciudad"] if c in v.columns]
    return v.groupby(["id_cliente"] + extra, as_index=False).agg(
        total_compras   = ("total_venta", "sum"),
        num_transacc    = ("id_venta",    "count"),
        ticket_promedio = ("total_venta", "mean")
    ).sort_values("total_compras", ascending=False)

def metrica_canal(v):
    df = v.groupby("canal", as_index=False).agg(
        total_ventas  = ("total_venta", "sum"),
        transacciones = ("id_venta",    "count")
    )
    df["porcentaje"] = (df["total_ventas"] / df["total_ventas"].sum() * 100).round(1)
    return df.sort_values("total_ventas", ascending=False)

def metrica_producto(v):
    if "nombre_producto" not in v.columns:
        return None
    df = v.dropna(subset=["id_producto"])
    if df.empty:
        return None
    return df.groupby(["id_producto", "nombre_producto", "categoria"], as_index=False).agg(
        total_ventas = ("total_venta", "sum"),
        unidades     = ("cantidad",    "sum")
    ).sort_values("total_ventas", ascending=False)

def metrica_categoria(v):
    if "categoria" not in v.columns:
        return None
    df = v.dropna(subset=["categoria"])
    if df.empty:
        return None
    return df.groupby("categoria", as_index=False).agg(
        total_ventas  = ("total_venta", "sum"),
        transacciones = ("id_venta",    "count")
    ).sort_values("total_ventas", ascending=False)

def metrica_fecha(v):
    return v.groupby("fecha", as_index=False).agg(
        total_ventas  = ("total_venta", "sum"),
        transacciones = ("id_venta",    "count")
    ).sort_values("fecha")


def run(fecha: str = None):
    if fecha is None:
        fecha = sys.argv[1] if len(sys.argv) > 1 else "maestros"

    if fecha == "maestros":
        _log(">> Procesamiento [maestros]: sin ventas que consolidar — omitido")
        return {}

    fecha_dir    = get_dir("transformed", fecha)
    maestros_dir = get_dir("transformed", "maestros")
    integrated_dir = get_dir("integrated", fecha)

    ventas = consolidar_ventas(fecha_dir)
    if ventas is None:
        _log(f">> Procesamiento [{fecha}]: sin datos de ventas — omitido")
        return {}

    ventas_enriq = enriquecer(ventas, fecha_dir, maestros_dir)

    resultados = {
        "ventas_consolidadas": ventas,
        "ventas_enriquecidas": ventas_enriq,
    }

    metricas = {
        "metricas_clientes":  metrica_clientes(ventas_enriq),
        "metricas_canal":     metrica_canal(ventas_enriq),
        "metricas_producto":  metrica_producto(ventas_enriq),
        "metricas_categoria": metrica_categoria(ventas_enriq),
        "metricas_fecha":     metrica_fecha(ventas_enriq),
    }
    for nombre, df in metricas.items():
        if df is not None and len(df) > 0:
            resultados[nombre] = df

    for nombre, df in resultados.items():
        df.to_csv(os.path.join(integrated_dir, f"{nombre}.csv"), index=False)

    _log(f">> Procesamiento [{fecha}]: {len(resultados)} datasets generados ({len(ventas)} ventas)")
    return resultados


if __name__ == "__main__":
    run()