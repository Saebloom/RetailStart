# ============================================================
#  RetailStart Chile S.A. — Data Platform
#  Archivo : scripts/warehouse/load.py
#  Etapa   : Carga al Data Warehouse (PostgreSQL)
#            integrated/ → tablas dw.*
# ============================================================
 
import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values
 
load_dotenv()
 
# ------------------------------------------------------------
# Rutas base
# ------------------------------------------------------------
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INTEGRATED = os.path.join(BASE_DIR, "data", "processed", "integrated")
TRANSFORMED = os.path.join(BASE_DIR, "data", "processed", "transformed")
 
 
def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
 
 
# ============================================================
#  CONEXIÓN A POSTGRESQL
# ============================================================
 
def conectar():
    conn = psycopg2.connect(
        host     = os.getenv("DB_HOST",     "localhost"),
        port     = os.getenv("DB_PORT",     "5432"),
        dbname   = os.getenv("DB_NAME",     "retailstart_dw"),
        user     = os.getenv("DB_USER",     "postgres"),
        password = os.getenv("DB_PASSWORD", "")
    )
    conn.autocommit = False
    _log("Conexión a PostgreSQL exitosa")
    return conn
 
 
# ============================================================
#  CARGA DE DIMENSIONES
# ============================================================
 
def cargar_dim_cliente(conn):
    _log(">> Cargando dim_cliente...")
    df = pd.read_csv(os.path.join(TRANSFORMED, "clientes_crm_clean.csv"))
 
    registros = [
        (
            int(row["id_cliente"]),
            str(row["nombre"]),
            str(row["apellido"]),
            str(row["email"]),
            str(row["segmento"]),
            str(row["ciudad"])
        )
        for _, row in df.iterrows()
    ]
 
    sql = """
        INSERT INTO dw.dim_cliente
            (id_cliente, nombre, apellido, email, segmento, ciudad)
        VALUES %s
        ON CONFLICT (id_cliente) DO UPDATE SET
            nombre   = EXCLUDED.nombre,
            apellido = EXCLUDED.apellido,
            email    = EXCLUDED.email,
            segmento = EXCLUDED.segmento,
            ciudad   = EXCLUDED.ciudad;
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, registros)
    _log(f"  {len(registros)} clientes cargados")
 
 
def cargar_dim_producto(conn):
    _log(">> Cargando dim_producto...")
    df = pd.read_csv(os.path.join(TRANSFORMED, "productos_erp_clean.csv"))
 
    registros = [
        (
            int(row["id_producto"]),
            str(row["nombre_producto"]),
            str(row["categoria"]),
            float(row["precio_base"]),
            str(row["proveedor"])
        )
        for _, row in df.iterrows()
    ]
 
    sql = """
        INSERT INTO dw.dim_producto
            (id_producto, nombre_producto, categoria, precio_base, proveedor)
        VALUES %s
        ON CONFLICT (id_producto) DO UPDATE SET
            nombre_producto = EXCLUDED.nombre_producto,
            categoria       = EXCLUDED.categoria,
            precio_base     = EXCLUDED.precio_base,
            proveedor       = EXCLUDED.proveedor;
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, registros)
    _log(f"  {len(registros)} productos cargados")
 
 
def cargar_dim_tiempo(conn):
    _log(">> Cargando dim_tiempo...")
    df = pd.read_csv(os.path.join(INTEGRATED, "ventas_consolidadas.csv"))
    df["fecha"] = pd.to_datetime(df["fecha"])
 
    fechas_unicas = df["fecha"].dt.date.unique()
 
    dias_semana = {
        0: "Lunes", 1: "Martes", 2: "Miércoles",
        3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"
    }
 
    registros = []
    for fecha in fechas_unicas:
        dt = pd.Timestamp(fecha)
        registros.append((
            str(fecha),
            int(dt.day),
            int(dt.month),
            int(dt.year),
            dias_semana[dt.dayofweek],
            dt.dayofweek >= 5
        ))
 
    sql = """
        INSERT INTO dw.dim_tiempo
            (fecha, dia, mes, anio, dia_semana, es_finde)
        VALUES %s
        ON CONFLICT (fecha) DO NOTHING;
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, registros)
    _log(f"  {len(registros)} fechas cargadas")
 
 
def cargar_dim_tienda(conn):
    _log(">> Cargando dim_tienda...")
 
    # Tiendas desde ventas_pos
    df = pd.read_csv(os.path.join(TRANSFORMED, "ventas_pos_clean.csv"))
    tiendas = df["tienda"].dropna().unique()
 
    sql = """
        INSERT INTO dw.dim_tienda (nombre_tienda, ciudad, region)
        VALUES %s
        ON CONFLICT DO NOTHING;
    """
    registros = [(t, t, "Metropolitana") for t in tiendas]
 
    with conn.cursor() as cur:
        execute_values(cur, sql, registros)
    _log(f"  {len(registros)} tiendas verificadas")
 
 
# ============================================================
#  CARGA DE HECHOS
# ============================================================
 
def obtener_id_tiempo(cur, fecha: str) -> int:
    cur.execute("SELECT id_tiempo FROM dw.dim_tiempo WHERE fecha = %s", (fecha,))
    row = cur.fetchone()
    return row[0] if row else None
 
 
def obtener_id_canal(cur, tipo_canal: str) -> int:
    cur.execute("SELECT id_canal FROM dw.dim_canal WHERE tipo_canal = %s", (tipo_canal,))
    row = cur.fetchone()
    return row[0] if row else None
 
 
def obtener_id_tienda(cur, nombre: str) -> int:
    if not nombre or str(nombre) == "nan":
        return None
    cur.execute("SELECT id_tienda FROM dw.dim_tienda WHERE nombre_tienda = %s", (str(nombre),))
    row = cur.fetchone()
    return row[0] if row else None
 
 
def cargar_fact_ventas(conn):
    _log(">> Cargando fact_ventas...")
    df = pd.read_csv(os.path.join(INTEGRATED, "ventas_enriquecidas.csv"))
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
 
    registros = []
    with conn.cursor() as cur:
        for _, row in df.iterrows():
            id_tiempo  = obtener_id_tiempo(cur, str(row["fecha"]))
            id_canal   = obtener_id_canal(cur, str(row["canal"]))
            id_tienda  = obtener_id_tienda(cur, row.get("tienda"))
 
            id_producto = None if pd.isna(row.get("id_producto")) else int(row["id_producto"])
 
            registros.append((
                id_tiempo,
                int(row["id_cliente"]),
                id_producto,
                id_canal,
                id_tienda,
                int(row["cantidad"])       if not pd.isna(row["cantidad"])       else 1,
                float(row["precio_unitario"]) if not pd.isna(row["precio_unitario"]) else 0.0,
                float(row["total_venta"]),
                str(row["fuente"]),
                int(row["id_venta"])
            ))
 
    sql = """
        INSERT INTO dw.fact_ventas
            (id_tiempo_fk, id_cliente_fk, id_producto_fk, id_canal_fk,
             id_tienda_fk, cantidad, precio_unitario, total_venta,
             fuente, id_origen)
        VALUES %s;
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, registros)
    _log(f"  {len(registros)} registros cargados en fact_ventas")
 
 
# ============================================================
#  FUNCIÓN PRINCIPAL
# ============================================================
 
def run():
    _log("=" * 50)
    _log("INICIO CARGA AL DATA WAREHOUSE")
    _log("=" * 50)
 
    conn = conectar()
 
    try:
        # Limpiar tablas antes de cargar (para evitar duplicados en re-ejecuciones)
        _log("")
        _log(">> Limpiando tablas existentes...")
        with conn.cursor() as cur:
            cur.execute("TRUNCATE dw.fact_ventas RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE dw.dim_cliente RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE dw.dim_producto RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE dw.dim_tiempo RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE dw.dim_tienda RESTART IDENTITY CASCADE;")
        _log("  Tablas limpiadas")
 
        # Cargar dimensiones primero
        _log("")
        _log(">> CARGANDO DIMENSIONES:")
        _log("-" * 40)
        cargar_dim_cliente(conn)
        cargar_dim_producto(conn)
        cargar_dim_tiempo(conn)
        cargar_dim_tienda(conn)
 
        # Cargar hechos después
        _log("")
        _log(">> CARGANDO TABLA DE HECHOS:")
        _log("-" * 40)
        cargar_fact_ventas(conn)
 
        # Confirmar transacción
        conn.commit()
        _log("")
        _log("=" * 50)
        _log("CARGA COMPLETA — Datos disponibles en PostgreSQL")
        _log("=" * 50)
 
    except Exception as e:
        conn.rollback()
        _log(f"ERROR: {e}")
        raise
 
    finally:
        conn.close()
        _log("Conexión cerrada")
 
 
# ============================================================
#  Ejecución directa
# ============================================================
if __name__ == "__main__":
    run()