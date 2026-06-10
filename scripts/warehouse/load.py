# ============================================================
#  RetailStart Chile S.A. — Data Platform
#  Archivo : scripts/warehouse/load.py
#  Versión : 3.0 — con soporte de fecha como argumento
#  Uso     : python load.py [fecha]
# ============================================================

import os
import sys
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values

load_dotenv(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def get_integrated(fecha: str) -> str:
    return os.path.join(BASE_DIR, "data", "processed", "integrated", fecha)


def get_transformed(fecha: str) -> str:
    return os.path.join(BASE_DIR, "data", "processed", "transformed", fecha)


def cargar_csv(carpeta: str, nombre: str) -> pd.DataFrame | None:
    ruta = os.path.join(carpeta, nombre)
    if not os.path.isfile(ruta):
        return None
    return pd.read_csv(ruta)


def conectar():
    conn = psycopg2.connect(
        host     = os.getenv("DB_HOST",     "localhost"),
        port     = os.getenv("DB_PORT",     "5432"),
        dbname   = os.getenv("DB_NAME",     "retailstart_dw"),
        user     = os.getenv("DB_USER",     "postgres"),
        password = os.getenv("DB_PASSWORD", "")
    )
    conn.autocommit = False
    _log("Conexion a PostgreSQL exitosa")
    return conn


# ── Dimensiones ──────────────────────────────────────────────

def cargar_dim_cliente(conn, transformed_dir: str):
    df = cargar_csv(transformed_dir, "clientes_crm_clean.csv")
    if df is None:
        _log("  dim_cliente — omitida")
        return
    registros = [
        (int(r["id_cliente"]), str(r["nombre"]), str(r["apellido"]),
         str(r["email"]), str(r["segmento"]), str(r["ciudad"]))
        for _, r in df.iterrows()
    ]
    sql = """
        INSERT INTO dw.dim_cliente
            (id_cliente, nombre, apellido, email, segmento, ciudad)
        VALUES %s
        ON CONFLICT (id_cliente) DO UPDATE SET
            nombre=EXCLUDED.nombre, apellido=EXCLUDED.apellido,
            email=EXCLUDED.email,   segmento=EXCLUDED.segmento,
            ciudad=EXCLUDED.ciudad;
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, registros)
    _log(f"  dim_cliente — {len(registros)} registros cargados")


def cargar_dim_producto(conn, transformed_dir: str):
    df = cargar_csv(transformed_dir, "productos_erp_clean.csv")
    if df is None:
        _log("  dim_producto — omitida")
        return
    registros = [
        (int(r["id_producto"]), str(r["nombre_producto"]),
         str(r["categoria"]), float(r["precio_base"]), str(r["proveedor"]))
        for _, r in df.iterrows()
    ]
    sql = """
        INSERT INTO dw.dim_producto
            (id_producto, nombre_producto, categoria, precio_base, proveedor)
        VALUES %s
        ON CONFLICT (id_producto) DO UPDATE SET
            nombre_producto=EXCLUDED.nombre_producto,
            categoria=EXCLUDED.categoria,
            precio_base=EXCLUDED.precio_base,
            proveedor=EXCLUDED.proveedor;
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, registros)
    _log(f"  dim_producto — {len(registros)} registros cargados")


def cargar_dim_tiempo(conn, integrated_dir: str):
    df = cargar_csv(integrated_dir, "ventas_consolidadas.csv")
    if df is None:
        _log("  dim_tiempo — omitida")
        return
    df["fecha"] = pd.to_datetime(df["fecha"])
    dias = {0:"Lunes",1:"Martes",2:"Miercoles",3:"Jueves",
            4:"Viernes",5:"Sabado",6:"Domingo"}
    registros = []
    for fecha in df["fecha"].dt.date.unique():
        dt = pd.Timestamp(fecha)
        registros.append((
            str(fecha), int(dt.day), int(dt.month),
            int(dt.year), dias[dt.dayofweek], dt.dayofweek >= 5
        ))
    sql = """
        INSERT INTO dw.dim_tiempo (fecha, dia, mes, anio, dia_semana, es_finde)
        VALUES %s ON CONFLICT (fecha) DO NOTHING;
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, registros)
    _log(f"  dim_tiempo — {len(registros)} fechas cargadas")


def cargar_dim_tienda(conn, transformed_dir: str):
    df = cargar_csv(transformed_dir, "ventas_pos_clean.csv")
    if df is None:
        _log("  dim_tienda — omitida (sin ventas POS)")
        return
    tiendas = df["tienda"].dropna().unique()
    registros = [(t, t, "Metropolitana") for t in tiendas]
    sql = """
        INSERT INTO dw.dim_tienda (nombre_tienda, ciudad, region)
        VALUES %s ON CONFLICT DO NOTHING;
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, registros)
    _log(f"  dim_tienda — {len(registros)} tiendas verificadas")


# ── Helpers fact_ventas ──────────────────────────────────────

def get_id_tiempo(cur, fecha: str):
    cur.execute("SELECT id_tiempo FROM dw.dim_tiempo WHERE fecha = %s", (fecha,))
    row = cur.fetchone()
    return row[0] if row else None


def get_id_canal(cur, tipo: str):
    cur.execute("SELECT id_canal FROM dw.dim_canal WHERE tipo_canal = %s", (tipo,))
    row = cur.fetchone()
    return row[0] if row else None


def get_id_tienda(cur, nombre):
    if not nombre or str(nombre) == "nan":
        return None
    cur.execute("SELECT id_tienda FROM dw.dim_tienda WHERE nombre_tienda = %s", (str(nombre),))
    row = cur.fetchone()
    return row[0] if row else None


def get_id_producto(cur, id_prod):
    if pd.isna(id_prod):
        return None
    cur.execute("SELECT id_producto FROM dw.dim_producto WHERE id_producto = %s", (int(id_prod),))
    row = cur.fetchone()
    return row[0] if row else None


def cargar_fact_ventas(conn, integrated_dir: str):
    df = cargar_csv(integrated_dir, "ventas_enriquecidas.csv")
    if df is None:
        _log("  fact_ventas — omitida")
        return

    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    registros   = []
    omitidos    = 0

    with conn.cursor() as cur:
        for _, row in df.iterrows():
            id_tiempo   = get_id_tiempo(cur, str(row["fecha"]))
            id_canal    = get_id_canal(cur, str(row["canal"]))
            id_tienda   = get_id_tienda(cur, row.get("tienda"))
            id_producto = get_id_producto(cur, row.get("id_producto"))

            if id_tiempo is None or id_canal is None:
                omitidos += 1
                continue

            registros.append((
                id_tiempo,
                int(row["id_cliente"]),
                id_producto,
                id_canal,
                id_tienda,
                int(row["cantidad"])          if not pd.isna(row["cantidad"])          else 1,
                float(row["precio_unitario"]) if not pd.isna(row["precio_unitario"])   else 0.0,
                float(row["total_venta"]),
                str(row["fuente"]),
                int(row["id_venta"])
            ))

    if not registros:
        _log("  fact_ventas — sin registros validos")
        return

    sql = """
        INSERT INTO dw.fact_ventas
            (id_tiempo_fk, id_cliente_fk, id_producto_fk, id_canal_fk,
             id_tienda_fk, cantidad, precio_unitario, total_venta,
             fuente, id_origen)
        VALUES %s;
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, registros)

    msg = f"  fact_ventas — {len(registros)} registros cargados"
    if omitidos:
        msg += f" ({omitidos} omitidos)"
    _log(msg)


# ── Principal ────────────────────────────────────────────────

def run(fecha: str = None):
    if fecha is None:
        fecha = sys.argv[1] if len(sys.argv) > 1 else "sin_fecha"

    integrated_dir  = get_integrated(fecha)
    transformed_dir = get_transformed(fecha)

    _log("=" * 50)
    _log(f"INICIO CARGA AL DATA WAREHOUSE — Fecha: {fecha}")
    _log("=" * 50)

    conn = conectar()

    try:
        _log("\n>> Cargando dimensiones:")
        cargar_dim_cliente(conn,  transformed_dir)
        cargar_dim_producto(conn, transformed_dir)
        cargar_dim_tiempo(conn,   integrated_dir)
        cargar_dim_tienda(conn,   transformed_dir)

        _log("\n>> Cargando tabla de hechos:")
        cargar_fact_ventas(conn, integrated_dir)

        conn.commit()
        _log("")
        _log("=" * 50)
        _log(f"CARGA COMPLETA — Fecha: {fecha}")
        _log("=" * 50)

    except Exception as e:
        conn.rollback()
        _log(f"ERROR: {e}")
        raise
    finally:
        conn.close()
        _log("Conexion cerrada")


if __name__ == "__main__":
    run()