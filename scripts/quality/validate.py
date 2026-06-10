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


# Limpiezas

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
    df["fecha"]  = pd.to_datetime(df["fecha"])
    df["total"]  = df["total"].astype(float)
    df["canal"]  = df["canal"].str.strip().str.lower()
    df["fuente"] = "online"
    return df.rename(columns={"id_orden": "id_venta", "total": "total_venta"})

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
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"])
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


LIMPIEZAS = {
    "ventas_pos":     limpiar_ventas_pos,
    "ventas_online":  limpiar_ventas_online,
    "clientes_crm":   limpiar_clientes,
    "productos_erp":  limpiar_productos,
    "logistica":      limpiar_logistica,
    "eventos_app":    limpiar_eventos_app,
    "callcenter":     limpiar_callcenter,
    "redes_sociales": limpiar_redes_sociales,
    "proveedores":    limpiar_generica,
    "multimedia":     limpiar_generica,
    "logs_sistema":   limpiar_generica,
}


def run(fecha: str = None):
    if fecha is None:
        fecha = sys.argv[1] if len(sys.argv) > 1 else "maestros"

    cdir = get_dir("cleaned", fecha)
    tdir = get_dir("transformed", fecha)

    disponibles = [n for n in LIMPIEZAS if os.path.isfile(os.path.join(cdir, f"{n}_raw.csv"))]

    if not disponibles:
        _log(f">> Validacion [{fecha}]: sin archivos")
        return {}

    limpios = {}
    for nombre in disponibles:
        df = pd.read_csv(os.path.join(cdir, f"{nombre}_raw.csv"))
        df = LIMPIEZAS[nombre](df)
        df.to_csv(os.path.join(tdir, f"{nombre}_clean.csv"), index=False)
        limpios[nombre] = df

    _log(f">> Validacion [{fecha}]: {len(limpios)} datasets limpios ({', '.join(limpios.keys())})")
    return limpios


if __name__ == "__main__":
    run()