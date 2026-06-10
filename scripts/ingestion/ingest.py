import os
import sys
import pandas as pd
from lxml import etree
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_CSV  = os.path.join(BASE_DIR, "data", "raw", "csv")
RAW_JSON = os.path.join(BASE_DIR, "data", "raw", "json")
RAW_XML  = os.path.join(BASE_DIR, "data", "raw", "xml")
RAW_TXT  = os.path.join(BASE_DIR, "data", "raw", "txt")

DATASETS_FECHA   = ["ventas_pos", "ventas_online", "callcenter"]
DATASETS_MAESTRO_CSV = ["clientes_crm", "productos_erp", "proveedores", "multimedia"]
DATASETS_OTROS = {
    "eventos_app":    ("json", RAW_JSON),
    "redes_sociales": ("json", RAW_JSON),
    "logistica":      ("xml",  RAW_XML),
    "logs_sistema":   ("txt",  RAW_TXT),
}

def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def cleaned_dir(fecha: str) -> str:
    ruta = os.path.join(BASE_DIR, "data", "processed", "cleaned", fecha)
    os.makedirs(ruta, exist_ok=True)
    return ruta

def leer_xml(ruta: str) -> pd.DataFrame:
    tree = etree.parse(ruta)
    root = tree.getroot()
    registros = []
    for pedido in root.findall("pedido"):
        registros.append({
            "id_pedido":  int(pedido.find("id").text),
            "id_cliente": int(pedido.find("cliente").text),
            "estado":     pedido.find("estado").text.strip()
        })
    return pd.DataFrame(registros)

def leer_txt(ruta: str) -> pd.DataFrame:
    registros = []
    with open(ruta, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            partes = linea.split(" ", 3)
            registros.append({
                "fecha":   partes[0] if len(partes) > 0 else None,
                "hora":    partes[1] if len(partes) > 1 else None,
                "accion":  partes[2] if len(partes) > 2 else None,
                "detalle": partes[3] if len(partes) > 3 else None
            })
    return pd.DataFrame(registros)


def run(fecha: str = None):
    if fecha is None:
        fecha = sys.argv[1] if len(sys.argv) > 1 else "maestros"

    cdir = cleaned_dir(fecha)
    datasets = {}

    if fecha == "maestros":
        # Datasets maestros CSV — ya segmentados por watcher en cleaned/maestros/
        for nombre in DATASETS_MAESTRO_CSV:
            ruta = os.path.join(cdir, f"{nombre}_raw.csv")
            if os.path.isfile(ruta):
                df = pd.read_csv(ruta)
                datasets[nombre] = df

        # Datasets JSON/XML/TXT — leer directo desde raw/
        for nombre, (formato, carpeta) in DATASETS_OTROS.items():
            ruta = os.path.join(carpeta, f"{nombre}.{formato}")
            if not os.path.isfile(ruta):
                continue
            if formato == "json":
                df = pd.read_json(ruta)
            elif formato == "xml":
                df = leer_xml(ruta)
            else:
                df = leer_txt(ruta)
            df.to_csv(os.path.join(cdir, f"{nombre}_raw.csv"), index=False)
            datasets[nombre] = df

    else:
        # Datasets de ventas — ya segmentados por watcher en cleaned/<fecha>/
        for nombre in DATASETS_FECHA:
            ruta = os.path.join(cdir, f"{nombre}_raw.csv")
            if os.path.isfile(ruta):
                datasets[nombre] = pd.read_csv(ruta)

    _log(f">> Ingesta [{fecha}]: {len(datasets)} datasets ({', '.join(datasets.keys())})")
    return datasets


if __name__ == "__main__":
    run()