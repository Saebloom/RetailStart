import os
import shutil
import time
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

load_dotenv()

# ------------------------------------------------------------
# Rutas base
# ------------------------------------------------------------
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INBOX     = os.path.join(BASE_DIR, "data", "inbox")
RAW_CSV   = os.path.join(BASE_DIR, "data", "raw", "csv")
RAW_JSON  = os.path.join(BASE_DIR, "data", "raw", "json")
RAW_XML   = os.path.join(BASE_DIR, "data", "raw", "xml")
RAW_TXT   = os.path.join(BASE_DIR, "data", "raw", "txt")

# Mapeo extensión → carpeta destino
DESTINOS = {
    ".csv":  RAW_CSV,
    ".json": RAW_JSON,
    ".xml":  RAW_XML,
    ".txt":  RAW_TXT,
}

# Scripts del pipeline en orden
PIPELINE = [
    os.path.join(BASE_DIR, "scripts", "ingestion",  "ingest.py"),
    os.path.join(BASE_DIR, "scripts", "quality",    "validate.py"),
    os.path.join(BASE_DIR, "scripts", "processing", "transform.py"),
    os.path.join(BASE_DIR, "scripts", "warehouse",  "load.py"),
    os.path.join(BASE_DIR, "scripts", "analytics",  "visualize.py"),
]


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def crear_carpetas():
    """Crea inbox/ y todas las carpetas raw/ si no existen."""
    carpetas = [INBOX, RAW_CSV, RAW_JSON, RAW_XML, RAW_TXT]
    for c in carpetas:
        os.makedirs(c, exist_ok=True)


def clasificar_archivo(ruta_archivo: str) -> str | None:
    """
    Determina la carpeta destino según la extensión del archivo.
    Retorna la ruta destino o None si la extensión no es reconocida.
    """
    _, ext = os.path.splitext(ruta_archivo)
    return DESTINOS.get(ext.lower())


def mover_archivo(origen: str, destino_dir: str) -> str:
    """
    Mueve el archivo desde inbox/ a su carpeta raw/ correspondiente.
    Si ya existe un archivo con el mismo nombre lo sobreescribe.
    Retorna la ruta final del archivo movido.
    """
    nombre = os.path.basename(origen)
    destino = os.path.join(destino_dir, nombre)
    shutil.move(origen, destino)
    return destino


def ejecutar_pipeline():
    """
    Ejecuta los scripts del pipeline en orden.
    Si alguno falla detiene la ejecución y muestra el error.
    """
    _log("")
    _log("=" * 50)
    _log("DISPARANDO PIPELINE AUTOMÁTICO")
    _log("=" * 50)

    for script in PIPELINE:
        nombre = os.path.basename(script)
        _log(f">> Ejecutando: {nombre}...")

        resultado = subprocess.run(
            ["python", script],
            capture_output=True,
            text=True
        )

        if resultado.returncode == 0:
            # Mostrar solo las líneas importantes del output
            for linea in resultado.stdout.splitlines():
                if any(k in linea for k in ["COMPLETO", "INICIO", "ERROR", "cargado", "Guardado", "exitosa"]):
                    _log(f"   {linea.strip()}")
            _log(f"   ✓ {nombre} completado")
        else:
            _log(f"   ✗ ERROR en {nombre}:")
            for linea in resultado.stderr.splitlines()[-5:]:
                _log(f"     {linea}")
            _log("Pipeline detenido por error. Corrija el problema y vuelva a soltar el archivo.")
            return False

    _log("")
    _log("=" * 50)
    _log("PIPELINE COMPLETADO EXITOSAMENTE")
    _log("Los gráficos están en dashboards/exports/")
    _log("Los datos están disponibles en PostgreSQL")
    _log("=" * 50)
    return True


# ============================================================
#  MANEJADOR DE EVENTOS
# ============================================================

class InboxHandler(FileSystemEventHandler):
    """
    Escucha eventos de creación de archivos en inbox/.
    Cuando detecta un archivo nuevo lo clasifica y
    dispara el pipeline completo.
    """

    def __init__(self):
        super().__init__()
        self.procesando = False  # evita disparos múltiples simultáneos

    def on_created(self, event):
        # Ignorar carpetas y archivos temporales
        if event.is_directory:
            return
        if os.path.basename(event.src_path).startswith("."):
            return
        if event.src_path.endswith(".tmp") or event.src_path.endswith("~"):
            return

        # Esperar brevemente para que el archivo termine de copiarse
        time.sleep(1)

        if self.procesando:
            _log(f"Pipeline en curso — archivo en cola: {os.path.basename(event.src_path)}")
            return

        self.procesando = True
        archivo = event.src_path
        nombre  = os.path.basename(archivo)

        _log("")
        _log(f"Archivo detectado: {nombre}")

        # Clasificar por extensión
        destino_dir = clasificar_archivo(archivo)

        if destino_dir is None:
            _log(f"  Extensión no reconocida — archivo ignorado: {nombre}")
            _log(f"  Extensiones válidas: .csv, .json, .xml, .txt")
            self.procesando = False
            return

        # Mover a raw/
        try:
            destino_final = mover_archivo(archivo, destino_dir)
            carpeta_rel   = os.path.relpath(destino_dir, BASE_DIR)
            _log(f"  Movido a: {carpeta_rel}/{nombre}")
        except Exception as e:
            _log(f"  Error al mover archivo: {e}")
            self.procesando = False
            return

        # Disparar pipeline
        ejecutar_pipeline()
        self.procesando = False

    def on_moved(self, event):
        """También detecta archivos que son arrastrados a inbox/."""
        if not event.is_directory and event.dest_path.startswith(INBOX):
            self.on_created(type('E', (), {
                'is_directory': False,
                'src_path': event.dest_path
            })())


# ============================================================
#  FUNCIÓN PRINCIPAL
# ============================================================

def run():
    crear_carpetas()

    _log("=" * 50)
    _log("WATCHER INICIADO — RetailStart Data Platform")
    _log("=" * 50)
    _log(f"Escuchando: data/inbox/")
    _log(f"Extensiones válidas: .csv | .json | .xml | .txt")
    _log(f"Destinos:")
    _log(f"  .csv  → data/raw/csv/")
    _log(f"  .json → data/raw/json/")
    _log(f"  .xml  → data/raw/xml/")
    _log(f"  .txt  → data/raw/txt/")
    _log("")
    _log("Suelta cualquier archivo en data/inbox/ para iniciar el pipeline.")
    _log("Presiona Ctrl+C para detener el watcher.")
    _log("=" * 50)

    handler  = InboxHandler()
    observer = Observer()
    observer.schedule(handler, path=INBOX, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        _log("")
        _log("Watcher detenido por el usuario.")
        observer.stop()

    observer.join()


# ============================================================
#  Ejecución directa
# ============================================================
if __name__ == "__main__":
    run()