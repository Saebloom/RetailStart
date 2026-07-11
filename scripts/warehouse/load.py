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


def get_dir(zona: str, fecha: str) -> str:
    return os.path.join(BASE_DIR, "data", "processed", zona, fecha)


def cargar_csv(carpeta: str, nombre: str) -> pd.DataFrame | None:
    ruta = os.path.join(carpeta, nombre)
    return pd.read_csv(ruta) if os.path.isfile(ruta) else None


def conectar():
    conn = psycopg2.connect(
        host     = os.getenv("DB_HOST",     "localhost"),
        port     = os.getenv("DB_PORT",     "5432"),
        dbname   = os.getenv("DB_NAME",     "retailstart_dw"),
        user     = os.getenv("DB_USER",     "postgres"),
        password = os.getenv("DB_PASSWORD", "")
    )
    conn.autocommit = False
    return conn


# ── Dimensiones ──────────────────────────────────────────────

def cargar_dim_cliente(conn, mdir: str) -> int:
    df = cargar_csv(mdir, "clientes_crm_clean.csv")
    if df is None:
        return 0
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
    return len(registros)


def cargar_dim_producto(conn, mdir: str) -> int:
    df = cargar_csv(mdir, "productos_erp_clean.csv")
    if df is None:
        return 0
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
    return len(registros)


def cargar_dim_tiempo(conn, idir: str) -> int:
    df = cargar_csv(idir, "ventas_consolidadas.csv")
    if df is None:
        return 0
    df["fecha"] = pd.to_datetime(df["fecha"])
    dias = {0:"Lunes", 1:"Martes", 2:"Miercoles", 3:"Jueves",
            4:"Viernes", 5:"Sabado", 6:"Domingo"}
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
    return len(registros)


def cargar_dim_tienda(conn, fdir: str) -> int:
    df = cargar_csv(fdir, "ventas_pos_clean.csv")
    if df is None:
        return 0
    tiendas = df["tienda"].dropna().unique()
    registros = [(t, t, "Metropolitana") for t in tiendas]
    sql = """
        INSERT INTO dw.dim_tienda (nombre_tienda, ciudad, region)
        VALUES %s ON CONFLICT DO NOTHING;
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, registros)
    return len(registros)


# ── Helpers fact_ventas ──────────────────────────────────────

def get_id_tiempo(cur, fecha: str):
    cur.execute("SELECT id_tiempo FROM dw.dim_tiempo WHERE fecha = %s", (fecha,))
    row = cur.fetchone()
    return row[0] if row else None


def get_id_canal(cur, tipo: str):
    cur.execute("SELECT id_canal FROM dw.dim_canal WHERE tipo_canal = %s", (tipo,))
    row = cur.fetchone()
    return row[0] if row else None


def get_id_tienda(cur, nombre, canal: str):
    """
    Retorna id_tienda siempre con valor:
    - Ventas POS  -> busca la tienda fisica por nombre
    - Ventas online (web/app) -> asigna la tienda 'Online'
    """
    if not nombre or str(nombre) == "nan":
        # Venta online: asignar tienda Online
        if canal in ("web", "app"):
            cur.execute(
                "SELECT id_tienda FROM dw.dim_tienda WHERE nombre_tienda = 'Online'"
            )
            row = cur.fetchone()
            return row[0] if row else None
        return None
    # Venta POS: buscar por nombre de tienda fisica
    cur.execute(
        "SELECT id_tienda FROM dw.dim_tienda WHERE nombre_tienda = %s",
        (str(nombre),)
    )
    row = cur.fetchone()
    return row[0] if row else None


def get_id_producto(cur, id_prod):
    if pd.isna(id_prod):
        return None
    cur.execute(
        "SELECT id_producto FROM dw.dim_producto WHERE id_producto = %s",
        (int(id_prod),)
    )
    row = cur.fetchone()
    return row[0] if row else None


def cargar_fact_ventas(conn, idir: str, fdir: str) -> tuple[int, int]:
    df = cargar_csv(idir, "ventas_enriquecidas.csv")
    if df is None:
        return 0, 0

    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    registros, omitidos = [], 0

    with conn.cursor() as cur:
        for _, row in df.iterrows():
            canal       = str(row["canal"])
            id_tiempo   = get_id_tiempo(cur, str(row["fecha"]))
            id_canal    = get_id_canal(cur, canal)
            id_tienda   = get_id_tienda(cur, row.get("tienda"), canal)
            id_producto = get_id_producto(cur, row.get("id_producto"))

            # Solo se omite si faltan tiempo o canal — tienda y producto siempre deben tener valor
            if id_tiempo is None or id_canal is None or id_tienda is None:
                omitidos += 1
                _log(f"  [OMITIDA] tiempo={id_tiempo} canal={id_canal} tienda={id_tienda}")
                continue

            registros.append((
                id_tiempo,
                int(row["id_cliente"]),
                id_producto,
                id_canal,
                id_tienda,
                int(row["cantidad"])          if not pd.isna(row["cantidad"])        else 1,
                float(row["precio_unitario"]) if not pd.isna(row["precio_unitario"]) else 0.0,
                float(row["total_venta"]),
                str(row["fuente"]),
                int(row["id_venta"])
            ))

    if not registros:
        return 0, omitidos

    sql = """
        INSERT INTO dw.fact_ventas
            (id_tiempo_fk, id_cliente_fk, id_producto_fk, id_canal_fk,
             id_tienda_fk, cantidad, precio_unitario, total_venta,
             fuente, id_origen)
        VALUES %s
        ON CONFLICT (fuente, id_origen) DO NOTHING;
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, registros)

    return len(registros), omitidos


# ── Principal ────────────────────────────────────────────────

def run(fecha: str = None):
    if fecha is None:
        fecha = sys.argv[1] if len(sys.argv) > 1 else "maestros"

    conn = conectar()

    try:
        if fecha == "maestros":
            mdir   = get_dir("transformed", "maestros")
            n_cli  = cargar_dim_cliente(conn, mdir)
            n_prod = cargar_dim_producto(conn, mdir)
            conn.commit()
            _log(f">> Carga [maestros]: clientes={n_cli} productos={n_prod}")

        else:
            fdir = get_dir("transformed", fecha)
            idir = get_dir("integrated",  fecha)

            n_tiempo        = cargar_dim_tiempo(conn, idir)
            n_tienda        = cargar_dim_tienda(conn, fdir)
            n_fact, n_omit  = cargar_fact_ventas(conn, idir, fdir)
            conn.commit()

            msg = f">> Carga [{fecha}]: fechas={n_tiempo} tiendas={n_tienda} ventas={n_fact}"
            if n_omit:
                msg += f" (omitidas={n_omit})"
            _log(msg)

    except Exception as e:
        conn.rollback()
        _log(f"[ERROR] {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run()