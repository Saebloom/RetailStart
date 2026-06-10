# ============================================================
#  RetailStart Chile S.A. — Data Platform
#  Archivo : scripts/ingestion/watcher.py
#  Etapa   : Orquestación automatizada con segmentación temporal
#  Versión : 2.0
#
#  Flujo:
#   inbox/ → raw/ (archivo completo)
#            processed/cleaned/FECHA/ (segmentado por día)
#            processed/transformed/FECHA/
#            processed/integrated/FECHA/ (con métricas)
#            PostgreSQL DW
# ============================================================

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

DESTINOS = {
    ".csv":  "csv",
    ".json": "json",
    ".xml":  "xml",
    ".txt":  "txt",
}

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
    """Ejecuta el pipeline completo pasando la fecha como argumento."""
    for script in PIPELINE:
        nombre = os.path.basename(script)
        _log(f"   >> Ejecutando: {nombre} [{fecha}]...")

        resultado = subprocess.run(
            ["python", script, fecha],
            capture_output=True,
            text=True
        )

        if resultado.returncode == 0:
            for linea in resultado.stdout.splitlines():
                if any(k in linea for k in [
                    "COMPLETO", "INICIO", "cargado", "Guardado",
                    "exitosa", "procesados", "omitida", "CARGA"
                ]):
                    _log(f"      {linea.strip()}")
            _log(f"   [OK] {nombre} completado")
        else:
            _log(f"   [ERROR] {nombre} para fecha {fecha}:")
            for linea in resultado.stderr.splitlines()[-5:]:
                _log(f"      {linea}")
            _log(f"   Pipeline abortado para el dia {fecha}.")
            return False
    return True


# ============================================================
#  MANEJADOR
# ============================================================

class InboxHandler(FileSystemEventHandler):

    def __init__(self):
        super().__init__()
        self.procesando = False

    def on_created(self, event):
        if event.is_directory:
            return
        nombre = os.path.basename(event.src_path)
        if nombre.startswith(".") or nombre.endswith(".tmp") or nombre.endswith("~"):
            return

        time.sleep(1.5)

        if self.procesando:
            _log(f"Watcher ocupado — en cola: {nombre}")
            return

        self.procesando = True
        ruta_origen = event.src_path
        _, ext = os.path.splitext(nombre)
        ext = ext.lower()

        _log("")
        _log("=" * 60)
        _log(f"ARCHIVO DETECTADO: {nombre}")
        _log("=" * 60)

        if ext not in DESTINOS:
            _log(f"Extension {ext} no soportada. Ignorado.")
            self.procesando = False
            return

        tipo = DESTINOS[ext]

        try:
            # ── Paso 1: copiar archivo original a raw/ (intacto) ──────
            destino_raw = os.path.join(RAW_DIR, tipo, nombre)
            os.makedirs(os.path.join(RAW_DIR, tipo), exist_ok=True)
            shutil.copy2(ruta_origen, destino_raw)
            _log(f"   Copiado a raw/{tipo}/{nombre} (archivo original intacto)")

            # ── Paso 2: procesar según tipo ───────────────────────────
            if ext == ".csv":
                df = pd.read_csv(ruta_origen)

                if "fecha" in df.columns:
                    df["fecha_clean"] = pd.to_datetime(df["fecha"]).dt.strftime("%Y-%m-%d")
                    fechas = sorted(df["fecha_clean"].unique())
                    _log(f"   Dias encontrados: {fechas}")

                    for fecha in fechas:
                        _log("")
                        _log(f"-- DIA: {fecha} " + "-" * 40)

                        # Segmentar y guardar en cleaned/FECHA/
                        df_dia = df[df["fecha_clean"] == fecha].drop(columns=["fecha_clean"])
                        cleaned_dir = os.path.join(
                            BASE_DIR, "data", "processed", "cleaned", fecha
                        )
                        os.makedirs(cleaned_dir, exist_ok=True)
                        df_dia.to_csv(
                            os.path.join(cleaned_dir, nombre.replace(".csv", "_raw.csv")),
                            index=False
                        )
                        _log(f"   Segmentado en cleaned/{fecha}/{nombre.replace('.csv','_raw.csv')}")

                        # Ejecutar pipeline para este día
                        exito = ejecutar_pipeline(fecha)
                        if not exito:
                            break

                else:
                    # Dataset maestro sin fecha (productos, clientes, etc.)
                    _log("   Dataset maestro (sin columna fecha) — guardando en cleaned/maestros/")
                    maestros_dir = os.path.join(
                        BASE_DIR, "data", "processed", "cleaned", "maestros"
                    )
                    os.makedirs(maestros_dir, exist_ok=True)
                    shutil.copy2(
                        ruta_origen,
                        os.path.join(maestros_dir, nombre.replace(".csv", "_raw.csv"))
                    )
                    _log(f"   Guardado en cleaned/maestros/{nombre.replace('.csv','_raw.csv')}")

            else:
                # JSON, XML, TXT — sin segmentación por fecha
                _log(f"   Formato {ext} — sin segmentacion temporal, procesando directo")
                ejecutar_pipeline("maestros")

            # ── Paso 3: limpiar inbox ─────────────────────────────────
            os.remove(ruta_origen)
            _log("")
            _log("=" * 60)
            _log("PROCESAMIENTO COMPLETADO EXITOSAMENTE")
            _log("=" * 60)

        except Exception as e:
            _log(f"[ERROR] {e}")

        self.procesando = False

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.startswith(INBOX):
            self.on_created(type("E", (), {
                "is_directory": False,
                "src_path": event.dest_path
            })())


# ============================================================
#  PRINCIPAL
# ============================================================

def run():
    crear_carpetas()

    _log("=" * 60)
    _log("WATCHER INICIADO — RetailStart Chile S.A.")
    _log("=" * 60)
    _log("Escuchando: data/inbox/")
    _log("CSV con fechas  -> segmentado por dia en cleaned/FECHA/")
    _log("CSV sin fechas  -> cleaned/maestros/ (datos maestros)")
    _log("JSON / XML / TXT -> raw/ directo")
    _log("Ctrl+C para detener.")
    _log("=" * 60)

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