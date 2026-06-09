import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values

load_dotenv(encoding="utf-8")

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INTEGRATED  = os.path.join(BASE_DIR, "data", "processed", "integrated")
TRANSFORMED = os.path.join(BASE_DIR, "data", "processed", "transformed")


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def existe_integrated(nombre: str) -> bool:
    return os.path.isfile(os.path.join(INTEGRATED, f"{nombre}.csv"))


def existe_transformed(nombre: str) -> bool:
    return os.path.isfile(os.path.join(TRANSFORMED, f"{nombre}_clean.csv"))


def cargar_integrated(nombre: str) -> pd.DataFrame | None:
    ruta = os.path.join(INTEGRATED, f"{nombre}.csv")
    if not os.path.isfile(ruta):
        return None
    return pd.read_csv(ruta)


def cargar_transformed(nombre: str) -> pd.DataFrame | None:
    ruta = os.path.join(TRANSFORMED, f"{nombre}_clean.csv")
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
    _log("Conexión a PostgreSQL exitosa")
    return conn


# ── Dimensiones ──────────────────────────────────────────────

def cargar_dim_cliente(conn):
    df = cargar_transformed("clientes_crm")
    if df is None:
        _log("  dim_cliente — omitida (sin datos)")
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
            nombre   = EXCLUDED.nombre,
            apellido = EXCLUDED.apellido,
            email    = EXCLUDED.email,
            segmento = EXCLUDED.segmento,
            ciudad   = EXCLUDED.ciudad;
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, registros)
    _log(f"  dim_cliente — {len(registros)} registros cargados")


def cargar_dim_producto(conn):
    df = cargar_transformed("productos_erp")
    if df is None:
        _log("  dim_producto — omitida (sin datos)")
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
            nombre_producto = EXCLUDED.nombre_producto,
            categoria       = EXCLUDED.categoria,
            precio_base     = EXCLUDED.precio_base,
            proveedor       = EXCLUDED.proveedor;
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, registros)
    _log(f"  dim_producto — {len(registros)} registros cargados")


def cargar_dim_tiempo(conn):
    df = cargar_integrated("ventas_consolidadas")
    if df is None:
        _log("  dim_tiempo — omitida (sin ventas consolidadas)")
        return
    df["fecha"] = pd.to_datetime(df["fecha"])
    dias_semana = {
        0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
        4: "Viernes", 5: "Sábado", 6: "Domingo"
    }
    registros = []
    for fecha in df["fecha"].dt.date.unique():
        dt = pd.Timestamp(fecha)
        registros.append((
            str(fecha), int(dt.day), int(dt.month),
            int(dt.year), dias_semana[dt.dayofweek], dt.dayofweek >= 5
        ))
    sql = """
        INSERT INTO dw.dim_tiempo (fecha, dia, mes, anio, dia_semana, es_finde)
        VALUES %s ON CONFLICT (fecha) DO NOTHING;
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, registros)
    _log(f"  dim_tiempo — {len(registros)} fechas cargadas")


def cargar_dim_tienda(conn):
    df = cargar_transformed("ventas_pos")
    if df is None:
        _log("  dim_tienda — sin ventas POS, solo tienda Online disponible")
        return
    tiendas = df["tienda"].dropna().unique()
    registros = [(t, t, "Metropolitana") for t in tiendas]
    sql = """
        INSERT INTO dw.dim_tienda (nombre_tienda, ciudad, region)
        VALUES %s ON CONFLICT DO NOTHING;
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, registros)
    _log(f"  dim_tienda — {len(registros)} tiendas físicas verificadas")


# ── Helpers para fact_ventas ─────────────────────────────────

def obtener_id_tiempo(cur, fecha: str) -> int | None:
    cur.execute("SELECT id_tiempo FROM dw.dim_tiempo WHERE fecha = %s", (fecha,))
    row = cur.fetchone()
    return row[0] if row else None


def obtener_id_canal(cur, tipo: str) -> int | None:
    cur.execute("SELECT id_canal FROM dw.dim_canal WHERE tipo_canal = %s", (tipo,))
    row = cur.fetchone()
    return row[0] if row else None


def obtener_id_tienda(cur, nombre, canal: str) -> int | None:
    """
    Retorna el id_tienda correspondiente.
    - Ventas POS: busca por nombre de tienda física.
    - Ventas online (web/app): usa la tienda 'Online' de dim_tienda.
    Nunca retorna None — siempre habrá una tienda asignada.
    """
    if not nombre or str(nombre) == "nan":
        # Venta online — asignar tienda 'Online'
        if canal in ("web", "app"):
            cur.execute(
                "SELECT id_tienda FROM dw.dim_tienda WHERE nombre_tienda = 'Online'"
            )
            row = cur.fetchone()
            return row[0] if row else None
        return None
    # Venta POS — buscar tienda física por nombre
    cur.execute(
        "SELECT id_tienda FROM dw.dim_tienda WHERE nombre_tienda = %s",
        (str(nombre),)
    )
    row = cur.fetchone()
    return row[0] if row else None


def obtener_id_producto(cur, id_producto) -> int | None:
    """
    Retorna el id_producto si existe en dim_producto.
    Retorna None para ventas online (sin desglose por producto).
    El campo id_producto_fk en fact_ventas admite NULL por diseño.
    """
    if pd.isna(id_producto):
        return None
    cur.execute(
        "SELECT id_producto FROM dw.dim_producto WHERE id_producto = %s",
        (int(id_producto),)
    )
    row = cur.fetchone()
    return row[0] if row else None


# ── Tabla de hechos ──────────────────────────────────────────

def cargar_fact_ventas(conn):
    df = cargar_integrated("ventas_enriquecidas")
    if df is None:
        _log("  fact_ventas — omitida (sin ventas enriquecidas)")
        return

    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    registros   = []
    omitidos    = 0

    with conn.cursor() as cur:
        for _, row in df.iterrows():
            id_tiempo   = obtener_id_tiempo(cur, str(row["fecha"]))
            id_canal    = obtener_id_canal(cur, str(row["canal"]))
            id_tienda   = obtener_id_tienda(cur, row.get("tienda"), str(row["canal"]))
            id_producto = obtener_id_producto(cur, row.get("id_producto"))

            # Solo saltar si faltan tiempo o canal — tienda y producto pueden ser None
            if id_tiempo is None or id_canal is None:
                omitidos += 1
                _log(f"  [OMITIDA] Faltan claves obligatorias: "
                     f"tiempo={id_tiempo} canal={id_canal}")
                continue

            registros.append((
                id_tiempo,
                int(row["id_cliente"]),
                id_producto,                    # NULL para ventas online — por diseño
                id_canal,
                id_tienda,                      # 'Online' para web/app
                int(row["cantidad"])        if not pd.isna(row["cantidad"])        else 1,
                float(row["precio_unitario"]) if not pd.isna(row["precio_unitario"]) else 0.0,
                float(row["total_venta"]),
                str(row["fuente"]),
                int(row["id_venta"])
            ))

    if not registros:
        _log("  fact_ventas — sin registros válidos para cargar")
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

    _log(f"  fact_ventas — {len(registros)} registros cargados"
         + (f" ({omitidos} omitidos por claves faltantes)" if omitidos else ""))


# ── Principal ────────────────────────────────────────────────

def run():
    _log("=" * 50)
    _log("INICIO CARGA AL DATA WAREHOUSE")
    _log("=" * 50)

    conn = conectar()

    try:
        _log("")
        _log(">> Limpiando tablas...")
        with conn.cursor() as cur:
            cur.execute("TRUNCATE dw.fact_ventas  RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE dw.dim_cliente  RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE dw.dim_producto RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE dw.dim_tiempo   RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE dw.dim_tienda   RESTART IDENTITY CASCADE;")
        _log("  Tablas limpiadas")

        _log("")
        _log(">> Cargando dimensiones:")
        cargar_dim_cliente(conn)
        cargar_dim_producto(conn)
        cargar_dim_tiempo(conn)
        cargar_dim_tienda(conn)

        _log("")
        _log(">> Cargando tabla de hechos:")
        cargar_fact_ventas(conn)

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


if __name__ == "__main__":
    run()