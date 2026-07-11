CREATE SCHEMA IF NOT EXISTS dw;
SET search_path TO dw;


-- ── dim_tiempo ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dw.dim_tiempo (
    id_tiempo   SERIAL       PRIMARY KEY,
    fecha       DATE         NOT NULL UNIQUE,
    dia         SMALLINT     NOT NULL,
    mes         SMALLINT     NOT NULL,
    anio        SMALLINT     NOT NULL,
    dia_semana  VARCHAR(10)  NOT NULL,
    es_finde    BOOLEAN      NOT NULL DEFAULT FALSE
);

COMMENT ON TABLE  dw.dim_tiempo          IS 'Dimension de tiempo — granularidad diaria';
COMMENT ON COLUMN dw.dim_tiempo.es_finde IS 'TRUE si el dia es sabado o domingo';


-- ── dim_cliente ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dw.dim_cliente (
    id_cliente  SERIAL        PRIMARY KEY,
    nombre      VARCHAR(100)  NOT NULL,
    apellido    VARCHAR(100)  NOT NULL,
    email       VARCHAR(150)  NOT NULL,
    segmento    VARCHAR(20)   NOT NULL,
    ciudad      VARCHAR(100)  NOT NULL
);

COMMENT ON TABLE  dw.dim_cliente          IS 'Dimension de clientes — fuente: CRM';
COMMENT ON COLUMN dw.dim_cliente.segmento IS 'Premium | Regular | Nuevo';


-- ── dim_producto ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dw.dim_producto (
    id_producto     SERIAL         PRIMARY KEY,
    nombre_producto VARCHAR(150)   NOT NULL,
    categoria       VARCHAR(50)    NOT NULL,
    precio_base     NUMERIC(12,2)  NOT NULL,
    proveedor       VARCHAR(100)   NOT NULL
);

COMMENT ON TABLE  dw.dim_producto           IS 'Dimension de productos — fuente: ERP';
COMMENT ON COLUMN dw.dim_producto.categoria IS 'Tecnologia | Vestuario | Hogar';


-- ── dim_canal ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dw.dim_canal (
    id_canal    SERIAL        PRIMARY KEY,
    tipo_canal  VARCHAR(20)   NOT NULL,
    descripcion VARCHAR(100)
);

COMMENT ON TABLE  dw.dim_canal            IS 'Dimension de canal de venta';
COMMENT ON COLUMN dw.dim_canal.tipo_canal IS 'tienda_fisica | web | app';

INSERT INTO dw.dim_canal (tipo_canal, descripcion) VALUES
    ('tienda_fisica', 'Venta en punto de venta fisico (POS)'),
    ('web',           'Venta a traves de la plataforma e-commerce'),
    ('app',           'Venta a traves de la aplicacion movil')
ON CONFLICT DO NOTHING;


-- ── dim_tienda ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dw.dim_tienda (
    id_tienda     SERIAL        PRIMARY KEY,
    nombre_tienda VARCHAR(150)  NOT NULL,
    ciudad        VARCHAR(100)  NOT NULL,
    region        VARCHAR(100)  NOT NULL DEFAULT 'Metropolitana'
);

COMMENT ON TABLE dw.dim_tienda IS 'Dimension de tiendas — incluye tienda virtual Online para ventas web/app';

INSERT INTO dw.dim_tienda (nombre_tienda, ciudad, region) VALUES
    ('Santiago Centro', 'Santiago',    'Metropolitana'),
    ('Providencia',     'Providencia', 'Metropolitana'),
    ('Maipu',           'Maipu',       'Metropolitana'),
    ('Las Condes',      'Las Condes',  'Metropolitana'),
    ('La Florida',      'La Florida',  'Metropolitana'),
    ('Puente Alto',     'Puente Alto', 'Metropolitana'),
    ('Nuñoa',           'Nuñoa',       'Metropolitana'),
    ('Online',          'N/A',         'N/A')
ON CONFLICT DO NOTHING;

COMMENT ON COLUMN dw.dim_tienda.nombre_tienda IS
    'Online = tienda virtual asignada a ventas web y app';


-- ── fact_ventas ──────────────────────────────────────────────
-- id_tienda_fk: NOT NULL — ventas online usan la tienda Online
-- id_producto_fk: NOT NULL — ventas online ahora incluyen id_producto
CREATE TABLE IF NOT EXISTS dw.fact_ventas (
    id_venta        SERIAL          PRIMARY KEY,

    id_tiempo_fk    INT             NOT NULL REFERENCES dw.dim_tiempo(id_tiempo),
    id_cliente_fk   INT             NOT NULL REFERENCES dw.dim_cliente(id_cliente),
    id_producto_fk  INT             NOT NULL REFERENCES dw.dim_producto(id_producto),
    id_canal_fk     INT             NOT NULL REFERENCES dw.dim_canal(id_canal),
    id_tienda_fk    INT             NOT NULL REFERENCES dw.dim_tienda(id_tienda),

    cantidad        SMALLINT        NOT NULL DEFAULT 1,
    precio_unitario NUMERIC(12,2)   NOT NULL,
    total_venta     NUMERIC(14,2)   NOT NULL,

    fuente          VARCHAR(20)     NOT NULL,
    id_origen       INT             NOT NULL
);

COMMENT ON TABLE  dw.fact_ventas           IS 'Tabla de hechos — consolida POS y e-commerce';
COMMENT ON COLUMN dw.fact_ventas.fuente    IS 'POS | online';
COMMENT ON COLUMN dw.fact_ventas.id_origen IS 'ID original en el sistema fuente';
COMMENT ON COLUMN dw.fact_ventas.id_tienda_fk  IS
    'Nunca NULL: ventas POS usan tienda fisica, ventas online usan tienda Online';
COMMENT ON COLUMN dw.fact_ventas.id_producto_fk IS
    'Nunca NULL: ventas_online ahora incluye id_producto en el dataset';


-- ── Indices ──────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_fv_tiempo   ON dw.fact_ventas(id_tiempo_fk);
CREATE INDEX IF NOT EXISTS idx_fv_cliente  ON dw.fact_ventas(id_cliente_fk);
CREATE INDEX IF NOT EXISTS idx_fv_producto ON dw.fact_ventas(id_producto_fk);
CREATE INDEX IF NOT EXISTS idx_fv_canal    ON dw.fact_ventas(id_canal_fk);
CREATE INDEX IF NOT EXISTS idx_fv_tienda   ON dw.fact_ventas(id_tienda_fk);
CREATE INDEX IF NOT EXISTS idx_fv_fuente   ON dw.fact_ventas(fuente);

-- Restriccion de unicidad: evita duplicados en re-ejecuciones del pipeline
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_fact_ventas_origen'
    ) THEN
        ALTER TABLE dw.fact_ventas
            ADD CONSTRAINT uq_fact_ventas_origen UNIQUE (fuente, id_origen);
    END IF;
END $$;