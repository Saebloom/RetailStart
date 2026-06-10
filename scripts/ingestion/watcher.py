import os
import shutil
import time
import subprocess
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INBOX    = os.path.join(BASE_DIR, "data", "inbox")
RAW_DIR  = os.path.join(BASE_DIR, "data", "raw")

DESTINOS = {".csv": "csv", ".json": "json", ".xml": "xml", ".txt": "txt"}

PIPELINE = [
    os.path.join(BASE_DIR, "scripts", "ingestion",  "ingest.py"),
    os.path.join(BASE_DIR, "scripts", "quality",    "validate.py"),
    os.path.join(BASE_DIR, "scripts", "processing", "transform.py"),
    os.path.join(BASE_DIR, "scripts", "warehouse",  "load.py"),
]


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def crear_carpetas():
    os.makedirs(INBOX, exist_ok=True)


def ejecutar_pipeline(fecha: str) -> bool:
    """Ejecuta el pipeline completo para una fecha o 'maestros'."""
    for script in PIPELINE:
        nombre = os.path.basename(script)
        resultado = subprocess.run(
            ["python", script, fecha],
            capture_output=True, text=True
        )
        if resultado.returncode == 0:
            for linea in resultado.stdout.splitlines():
                if linea.strip().startswith(">>") or "cargados" in linea or "COMPLETO" in linea:
                    _log(f"      {linea.strip()}")
        else:
            _log(f"   [ERROR] {nombre} ({fecha}):")
            for linea in resultado.stderr.splitlines()[-3:]:
                _log(f"      {linea}")
            return False
    return True

#  MANEJADOR

DATASETS_FECHA   = {"ventas_pos", "ventas_online", "callcenter"}


class InboxHandler(FileSystemEventHandler):

    def __init__(self):
        super().__init__()
        self.procesando = False

    def on_created(self, event):
        if event.is_directory:
            return
        nombre = os.path.basename(event.src_path)
        if nombre.startswith(".") or nombre.endswith((".tmp", "~")):
            return

        time.sleep(1.5)
        if self.procesando:
            _log(f"En cola: {nombre}")
            return

        self.procesando = True
        ruta_origen = event.src_path
        clave, ext = os.path.splitext(nombre)
        ext = ext.lower()

        _log("")
        _log(f"--- {nombre} ---")

        if ext not in DESTINOS:
            _log(f"  Extension no soportada, ignorado.")
            self.procesando = False
            return

        tipo = DESTINOS[ext]

        try:
            # Copiar siempre el original intacto a raw/
            destino_raw_dir = os.path.join(RAW_DIR, tipo)
            os.makedirs(destino_raw_dir, exist_ok=True)
            shutil.copy2(ruta_origen, os.path.join(destino_raw_dir, nombre))

            if ext == ".csv" and clave in DATASETS_FECHA:
                # Dataset con fecha: segmentar por dia 
                df = pd.read_csv(ruta_origen)
                df["fecha_clean"] = pd.to_datetime(df["fecha"]).dt.strftime("%Y-%m-%d")
                fechas = sorted(df["fecha_clean"].unique())
                _log(f"  Tipo: dataset de ventas — dias: {len(fechas)}")

                for fecha in fechas:
                    df_dia = df[df["fecha_clean"] == fecha].drop(columns=["fecha_clean"])
                    cdir = os.path.join(BASE_DIR, "data", "processed", "cleaned", fecha)
                    os.makedirs(cdir, exist_ok=True)
                    df_dia.to_csv(os.path.join(cdir, f"{clave}_raw.csv"), index=False)

                    _log(f"  [{fecha}] {len(df_dia)} registros -> pipeline")
                    if not ejecutar_pipeline(fecha):
                        break

            elif ext == ".csv":
                # Dataset maestro: una sola vez
                _log(f"  Tipo: dataset maestro")
                mdir = os.path.join(BASE_DIR, "data", "processed", "cleaned", "maestros")
                os.makedirs(mdir, exist_ok=True)
                shutil.copy2(ruta_origen, os.path.join(mdir, f"{clave}_raw.csv"))
                ejecutar_pipeline("maestros")

            else:
                # JSON / XML / TXT: van a maestros
                _log(f"  Tipo: dataset complementario ({ext})")
                ejecutar_pipeline("maestros")

            os.remove(ruta_origen)
            _log(f"  Completado.")

        except Exception as e:
            _log(f"  [ERROR] {e}")

        self.procesando = False

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.startswith(INBOX):
            self.on_created(type("E", (), {
                "is_directory": False, "src_path": event.dest_path
            })())

#  PRINCIPAL

def run():
    crear_carpetas()

    print("")
    print("=" * 60)
    print("  RetailStart Chile S.A. — Data Platform")
    print("  Watcher de ingesta automatica")
    print("=" * 60)
    print("  Carpeta monitoreada : data/inbox/")
    print("")
    print("  Datasets de ventas (segmentados por dia):")
    print("    ventas_pos.csv, ventas_online.csv, callcenter.csv")
    print("")
    print("  Datasets maestros (carga unica):")
    print("    clientes_crm.csv, productos_erp.csv,")
    print("    proveedores.csv, multimedia.csv,")
    print("    eventos_app.json, redes_sociales.json,")
    print("    logistica.xml, logs_sistema.txt")
    print("")
    print("  Suelta un archivo en data/inbox/ para iniciar.")
    print("  Ctrl+C para detener.")
    print("=" * 60)
    print("")

    handler  = InboxHandler()
    observer = Observer()
    observer.schedule(handler, path=INBOX, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        _log("Watcher detenido.")
        observer.stop()

    observer.join()


if __name__ == "__main__":
    run()