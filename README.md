# RetailStart Chile S.A. — Data Platform

Solución práctica de arquitectura de datos moderna para RetailStart Chile S.A.
Pipeline completo desde la ingesta de datos hasta la visualización en Power BI.

---

## Integrantes

- Valeska Aguirre
- Nicolas Espejo
- Andres Gonzalez
- Bastian Cabello

---

## Tecnologías utilizadas

| Etapa | Herramienta |
|---|---|
| Ingesta | Python + pandas |
| Data Lake | Carpetas locales |
| Calidad de datos | Python + pandas |
| Procesamiento | Python + pandas |
| Data Warehouse | PostgreSQL (pgAdmin) |
| Visualización | matplotlib + seaborn + Power BI Desktop |
| Control de versiones | GitHub |

---

## Estructura del proyecto

```
RetailStart-DataPlatform/
│
├── data/
│   ├── raw/                    # Datos fuente originales (no modificar)
│   │   ├── csv/
│   │   ├── json/
│   │   ├── xml/
│   │   ├── txt/
│   │   └── multimedia/
│   ├── processed/
│   │   ├── cleaned/            # Datos crudos validados (_raw.csv)
│   │   ├── transformed/        # Datos limpios (_clean.csv)
│   │   └── integrated/         # Datasets integrados y métricas
│   └── warehouse/
│       ├── fact_tables/
│       └── dimension_tables/
│
├── scripts/
│   ├── ingestion/
│   │   └── ingest.py           # Lectura de todas las fuentes
│   ├── quality/
│   │   └── validate.py         # Limpieza y validación de datos
│   ├── processing/
│   │   └── transform.py        # Transformación e integración
│   ├── warehouse/
│   │   └── load.py             # Carga a PostgreSQL
│   └── analytics/
│       └── visualize.py        # Generación de gráficos
│
├── database/
│   └── sql/
│       └── create_tables.sql   # Esquema del Data Warehouse
│
├── dashboards/
│   ├── powerbi/                # Archivo .pbix de Power BI
│   └── exports/                # Gráficos generados por Python
│
├── .env                        # Credenciales locales (NO subir a GitHub)
├── .env.example                # Plantilla de credenciales
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Requisitos previos

Antes de comenzar asegúrate de tener instalado:

- **Python 3.10 o superior** — python.org
- **PostgreSQL** — postgresql.org
- **pgAdmin 4** — pgadmin.org (viene incluido con PostgreSQL)
- **Power BI Desktop** — powerbi.microsoft.com (gratuito, requiere cuenta Microsoft)
- **Git** — git-scm.com

---

## Configuración inicial

### 1. Clonar el repositorio

```bash
git clone https://github.com/Saebloom/RetailStart.git
cd RetailStart
```

### 2. Crear entorno virtual (recomendado)

```bash
python -m venv venv
```

Activar en Windows:
```bash
venv\Scripts\activate
```

Activar en Mac/Linux:
```bash
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar credenciales

Abre el `.env` y edita:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=retailstart_dw
DB_USER=postgres
DB_PASSWORD=tu_password_aqui
```


### 5. Verificar datasets

Asegúrate de que los archivos fuente estén en sus carpetas correspondientes:

```
data/raw/csv/     → ventas_pos.csv, clientes_crm.csv, productos_erp.csv,
                    ventas_online.csv, callcenter.csv, proveedores.csv, multimedia.csv
data/raw/json/    → eventos_app.json, redes_sociales.json
data/raw/xml/     → logistica.xml
data/raw/txt/     → logs_sistema.txt
```

> ⚠️ **IMPORTANTE:** No modifiques los archivos en `data/raw/`. Son los datos fuente originales.

---

## Configuración de la base de datos

### 1. Crear la base de datos en pgAdmin

- Abre pgAdmin
- Click derecho en **Databases** → **Create** → **Database**
- Nombre: `retailstart_dw`
- Click **Save**

### 2. Crear las tablas del Data Warehouse

- Click en la base de datos `retailstart_dw`
- Menú superior: **Tools** → **Query Tool**
- Click en el ícono de carpeta 📁 → abre `database/sql/create_tables.sql`
- Click en **▶ Run** (o F5)
- Verifica que aparezca: `Query returned successfully`

### 3. Verificar las tablas

En el panel izquierdo expande:
`retailstart_dw` → `Schemas` → `dw` → `Tables`

Deberías ver 6 tablas:
- `dim_cliente`
- `dim_producto`
- `dim_tiempo`
- `dim_canal`
- `dim_tienda`
- `fact_ventas`

---

## Ejecución del pipeline

Ejecuta cada script en orden desde la raíz del proyecto:

### Paso 1 — Ingesta de datos
```bash
python scripts/ingestion/ingest.py
```
Lee todas las fuentes (CSV, JSON, XML, TXT) y las guarda en `data/processed/cleaned/`

### Paso 2 — Calidad de datos
```bash
python scripts/quality/validate.py
```
Limpia duplicados, corrige tipos de datos y guarda en `data/processed/transformed/`

### Paso 3 — Procesamiento
```bash
python scripts/processing/transform.py
```
Une datasets, calcula métricas y guarda en `data/processed/integrated/`

### Paso 4 — Carga al Data Warehouse
```bash
python scripts/warehouse/load.py
```
Carga los datos procesados a PostgreSQL

### Paso 5 — Visualización
```bash
python scripts/analytics/visualize.py
```
Genera 5 gráficos en `dashboards/exports/`

---

## Gráficos generados

| Archivo | Análisis |
|---|---|
| `01_mejores_clientes.png` | ¿Quiénes son los mejores clientes? |
| `02_ventas_por_canal.png` | ¿Qué canal vende más? |
| `03_productos_mas_vendidos.png` | ¿Qué producto tiene más ventas? |
| `04_ventas_por_categoria.png` | Ventas por categoría de producto |
| `05_evolucion_ventas.png` | Evolución diaria de ventas |

---

## Conexión Power BI

    ---------------- FASE DE PRUEBA AUN NO TERMINADO ----------------------------

### 1. Instalar driver PostgreSQL
- Descarga el driver desde: https://github.com/npgsql/npgsql/releases
- Instala el archivo `.msi`
- Reinicia Power BI Desktop

### 2. Conectar a la base de datos
- Abre Power BI Desktop
- **Obtener datos** → **Más...** → busca `PostgreSQL` → **Conectar**
- Servidor: `localhost`
- Base de datos: `retailstart_dw`
- Usuario: `postgres` — Contraseña: tu password

### 3. Cargar tablas
Selecciona las 6 tablas del schema `dw` y click **Cargar**

### 4. Verificar relaciones
En la vista **Modelo** verifica que existan las relaciones entre `fact_ventas` y todas las dimensiones. Si alguna falta, arrástrala manualmente.

### 5. Guardar el archivo
Guarda el dashboard en `dashboards/powerbi/retailstart_dashboard.pbix`

---

## Reset completo (para demo)

Si necesitas mostrar el flujo desde cero:

### 1. Limpiar la base de datos
En pgAdmin → Query Tool ejecuta:
```sql
DROP SCHEMA dw CASCADE;
```

### 2. Limpiar archivos procesados
Elimina el contenido de estas carpetas (no las carpetas, solo su contenido):
```
data/processed/cleaned/
data/processed/transformed/
data/processed/integrated/
```

### 3. Recrear tablas y correr pipeline
```bash
# Primero ejecutar create_tables.sql en pgAdmin
python scripts/ingestion/ingest.py
python scripts/quality/validate.py
python scripts/processing/transform.py
python scripts/warehouse/load.py
python scripts/analytics/visualize.py
```

---

## Advertencias

> ⚠️ **No modifiques los archivos en `data/raw/`.** Son los datos fuente originales. Cualquier modificación afecta todo el pipeline.

> ⚠️ **Ejecuta los scripts en orden.** Cada etapa depende de la anterior. Si saltas un paso el pipeline fallará.

> ⚠️ **El script `load.py` hace TRUNCATE automático** antes de cargar. Si lo ejecutas dos veces los datos anteriores se borran y se recargan.

> ⚠️ **Power BI requiere que PostgreSQL esté corriendo** al momento de conectarse. Verifica que el servicio esté activo antes de abrir el dashboard.

---

## Recomendaciones

> 💡 **Usa un entorno virtual** para evitar conflictos de librerías entre proyectos.

> 💡 **Haz commit frecuente** en GitHub. Usa mensajes descriptivos como `feat: agregar script de ingesta` o `fix: corregir tipos de datos en validate.py`.

> 💡 **No subas la carpeta `data/`** completa a GitHub si los archivos son grandes. Agrega las subcarpetas de `processed/` al `.gitignore` y sube solo los datos fuente de `raw/`.

> 💡 **Para la demo**, ten todo preparado de antemano: PostgreSQL corriendo, Power BI abierto y las carpetas `processed/` vacías.

> 💡 **Si un script falla**, revisa primero que el script anterior se haya ejecutado correctamente y que los archivos existan en la carpeta correspondiente.

---

## Flujo completo de la arquitectura

```
ORIGEN          INGESTA         ALMACENAMIENTO      PROCESAMIENTO     CONSUMO
──────          ───────         ──────────────      ─────────────     ───────
CSV             ingest.py  →    data/raw/       →   validate.py   →   Power BI
JSON        →   (Python)        data/cleaned/   →   transform.py  →   Gráficos
XML                             data/transform/ →   load.py       →   pgAdmin
TXT                             PostgreSQL DW
```

---

## Contacto

Proyecto desarrollado para el curso de Arquitectura de Datos — 2026
