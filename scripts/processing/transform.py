import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(encoding="utf-8")

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRANSFORMED = os.path.join(BASE_DIR, "data", "processed", "transformed")
INTEGRATED  = os.path.join(BASE_DIR, "data", "processed", "integrated")


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def cargar(nombre: str) -> pd.DataFrame | None:
    ruta = os.path.join(TRANSFORMED, f"{nombre}_clean.csv")
    if not os.path.isfile(ruta):
        return None
    return pd.read_csv(ruta)


def guardar(df: pd.DataFrame, nombre: str):
    os.makedirs(INTEGRATED, exist_ok=True)
    ruta = os.path.join(INTEGRATED, nombre)
    df.to_csv(ruta, index=False)
    _log(f"  Guardado: {nombre} ({len(df)} filas)")


# ── Paso 1: Consolidar ventas ────────────────────────────────

def consolidar_ventas() -> pd.DataFrame | None:
    pos    = cargar("ventas_pos")
    online = cargar("ventas_online")

    if pos is None and online is None:
        _log("  Sin datos de ventas disponibles — omitiendo consolidación")
        return None

    partes = []

    if pos is not None:
        pos_std = pos[["id_venta", "fecha", "id_cliente", "id_producto",
                        "cantidad", "precio_unitario", "total_venta", "fuente"]].copy()
        pos_std["canal"]  = "tienda_fisica"
        pos_std["tienda"] = pos["tienda"]
        partes.append(pos_std)
        _log(f"  ventas_pos: {len(pos)} registros")

    if online is not None:
        online_std = online[["id_venta", "fecha", "id_cliente",
                              "total_venta", "canal", "fuente"]].copy()
        online_std["id_producto"]     = None
        online_std["cantidad"]        = 1
        online_std["precio_unitario"] = online_std["total_venta"]
        online_std["tienda"]          = None
        partes.append(online_std)
        _log(f"  ventas_online: {len(online)} registros")

    ventas = pd.concat(partes, ignore_index=True)
    ventas["fecha"] = pd.to_datetime(ventas["fecha"])
    ventas = ventas.sort_values("fecha").reset_index(drop=True)
    _log(f"  Total consolidado: {len(ventas)} registros")
    return ventas


# ── Paso 2: Enriquecer ───────────────────────────────────────

def enriquecer_ventas(ventas: pd.DataFrame) -> pd.DataFrame:
    clientes  = cargar("clientes_crm")
    productos = cargar("productos_erp")

    if clientes is not None:
        ventas = ventas.merge(
            clientes[["id_cliente", "nombre", "apellido", "segmento", "ciudad"]],
            on="id_cliente", how="left"
        )
        _log("  Enriquecido con clientes")
    else:
        _log("  Sin clientes disponibles — omitiendo join")

    if productos is not None:
        ventas = ventas.merge(
            productos[["id_producto", "nombre_producto", "categoria"]],
            on="id_producto", how="left"
        )
        _log("  Enriquecido con productos")
    else:
        _log("  Sin productos disponibles — omitiendo join")

    return ventas


# ── Paso 3: Métricas ─────────────────────────────────────────

def ventas_por_cliente(ventas: pd.DataFrame) -> pd.DataFrame | None:
    cols = ["id_cliente", "total_venta", "id_venta"]
    extra = [c for c in ["nombre", "apellido", "segmento", "ciudad"] if c in ventas.columns]
    group_cols = ["id_cliente"] + extra
    if not all(c in ventas.columns for c in cols):
        return None
    return ventas.groupby(group_cols, as_index=False).agg(
        total_compras   = ("total_venta", "sum"),
        num_transacc    = ("id_venta",    "count"),
        ticket_promedio = ("total_venta", "mean")
    ).sort_values("total_compras", ascending=False)


def ventas_por_canal(ventas: pd.DataFrame) -> pd.DataFrame | None:
    if "canal" not in ventas.columns:
        return None
    return ventas.groupby("canal", as_index=False).agg(
        total_ventas  = ("total_venta", "sum"),
        transacciones = ("id_venta",    "count")
    ).assign(porcentaje=lambda df: (df["total_ventas"] / df["total_ventas"].sum() * 100).round(1)
    ).sort_values("total_ventas", ascending=False)


def ventas_por_producto(ventas: pd.DataFrame) -> pd.DataFrame | None:
    if "id_producto" not in ventas.columns or "nombre_producto" not in ventas.columns:
        return None
    return ventas.dropna(subset=["id_producto"]).groupby(
        ["id_producto", "nombre_producto", "categoria"], as_index=False
    ).agg(
        total_ventas = ("total_venta", "sum"),
        unidades     = ("cantidad",    "sum")
    ).sort_values("total_ventas", ascending=False)


def ventas_por_categoria(ventas: pd.DataFrame) -> pd.DataFrame | None:
    if "categoria" not in ventas.columns:
        return None
    return ventas.dropna(subset=["categoria"]).groupby(
        "categoria", as_index=False
    ).agg(
        total_ventas  = ("total_venta", "sum"),
        transacciones = ("id_venta",    "count")
    ).sort_values("total_ventas", ascending=False)


def ventas_por_fecha(ventas: pd.DataFrame) -> pd.DataFrame | None:
    if "fecha" not in ventas.columns:
        return None
    return ventas.groupby("fecha", as_index=False).agg(
        total_ventas  = ("total_venta", "sum"),
        transacciones = ("id_venta",    "count")
    ).sort_values("fecha")


def run() -> dict:
    _log("=" * 50)
    _log("INICIO PROCESAMIENTO DE DATOS")
    _log("=" * 50)

    resultados = {}

    # Paso 1 — Consolidar
    _log("")
    _log(">> Consolidando ventas...")
    ventas = consolidar_ventas()

    if ventas is None:
        _log("Sin datos de ventas — procesamiento omitido")
        return resultados

    guardar(ventas, "ventas_consolidadas.csv")
    resultados["ventas_consolidadas"] = ventas

    # Paso 2 — Enriquecer
    _log("")
    _log(">> Enriqueciendo ventas...")
    ventas_enriq = enriquecer_ventas(ventas)
    guardar(ventas_enriq, "ventas_enriquecidas.csv")
    resultados["ventas_enriquecidas"] = ventas_enriq

    # Paso 3 — Métricas
    _log("")
    _log(">> Generando métricas...")

    metricas = {
        "metricas_clientes":  ventas_por_cliente(ventas_enriq),
        "metricas_canal":     ventas_por_canal(ventas_enriq),
        "metricas_producto":  ventas_por_producto(ventas_enriq),
        "metricas_categoria": ventas_por_categoria(ventas_enriq),
        "metricas_fecha":     ventas_por_fecha(ventas_enriq),
    }

    for nombre, df in metricas.items():
        if df is not None:
            guardar(df, f"{nombre}.csv")
            resultados[nombre] = df
        else:
            _log(f"  Omitida: {nombre} (datos insuficientes)")

    # Preview de resultados disponibles
    if "metricas_clientes" in resultados:
        _log("")
        _log(">> Top 3 clientes:")
        for _, row in resultados["metricas_clientes"].head(3).iterrows():
            nombre = f"{row.get('nombre','?')} {row.get('apellido','')}"
            _log(f"   {nombre.strip()} — ${row['total_compras']:,.0f} ({int(row['num_transacc'])} transacciones)")

    if "metricas_canal" in resultados:
        _log("")
        _log(">> Ventas por canal:")
        for _, row in resultados["metricas_canal"].iterrows():
            _log(f"   {row['canal']} — ${row['total_ventas']:,.0f} ({row['porcentaje']}%)")

    if "metricas_producto" in resultados:
        _log("")
        _log(">> Top 3 productos:")
        for _, row in resultados["metricas_producto"].head(3).iterrows():
            _log(f"   {row['nombre_producto']} — ${row['total_ventas']:,.0f}")

    _log("")
    _log("=" * 50)
    _log(f"PROCESAMIENTO COMPLETO — {len(resultados)} datasets generados")
    _log("=" * 50)

    return resultados


if __name__ == "__main__":
    run()