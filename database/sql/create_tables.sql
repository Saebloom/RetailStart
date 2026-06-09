-- ------------------------------------------------------------
-- 0. Schema propio para el DW (opcional pero recomendado)
-- ------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS dw;
SET search_path TO dw;
 
 
-- ============================================================
--  DIMENSIONES
-- ============================================================
 
-- ------------------------------------------------------------
-- dim_tiempo
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dw.dim_tiempo (
    id_tiempo       SERIAL          PRIMARY KEY,
    fecha           DATE            NOT NULL UNIQUE,
    dia             SMALLINT        NOT NULL,   -- 1-31
    mes             SMALLINT        NOT NULL,   -- 1-12
    anio            SMALLINT        NOT NULL,
    dia_semana      VARCHAR(10)     NOT NULL,   -- Lunes … Domingo
    es_finde        BOOLEAN         NOT NULL DEFAULT FALSE
);
 
COMMENT ON TABLE  dw.dim_tiempo              IS 'Dimensión de tiempo — granularidad diaria';
COMMENT ON COLUMN dw.dim_tiempo.es_finde     IS 'TRUE si el día es sábado o domingo';
 
 
-- ------------------------------------------------------------
-- dim_cliente
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dw.dim_cliente (
    id_cliente      SERIAL          PRIMARY KEY,
    nombre          VARCHAR(100)    NOT NULL,
    apellido        VARCHAR(100)    NOT NULL,
    email           VARCHAR(150)    NOT NULL,
    segmento        VARCHAR(20)     NOT NULL,   -- Premium | Regular | Nuevo
    ciudad          VARCHAR(100)    NOT NULL
);
 
COMMENT ON TABLE  dw.dim_cliente             IS 'Dimensión de clientes — fuente: CRM';
COMMENT ON COLUMN dw.dim_cliente.segmento    IS 'Premium | Regular | Nuevo';
 
 
-- ------------------------------------------------------------
-- dim_producto
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dw.dim_producto (
    id_producto     SERIAL          PRIMARY KEY,
    nombre_producto VARCHAR(150)    NOT NULL,
    categoria       VARCHAR(50)     NOT NULL,   -- Tecnologia | Vestuario | Hogar
    precio_base     NUMERIC(12,2)   NOT NULL,
    proveedor       VARCHAR(100)    NOT NULL
);
 
COMMENT ON TABLE  dw.dim_producto            IS 'Dimensión de productos — fuente: ERP';
COMMENT ON COLUMN dw.dim_producto.categoria  IS 'Tecnologia | Vestuario | Hogar';
 
 
-- ------------------------------------------------------------
-- dim_canal
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dw.dim_canal (
    id_canal        SERIAL          PRIMARY KEY,
    tipo_canal      VARCHAR(20)     NOT NULL,   -- tienda_fisica | web | app
    descripcion     VARCHAR(100)
);
 
COMMENT ON TABLE  dw.dim_canal               IS 'Dimensión de canal de venta';
COMMENT ON COLUMN dw.dim_canal.tipo_canal    IS 'tienda_fisica | web | app';
 
-- Valores base
INSERT INTO dw.dim_canal (tipo_canal, descripcion) VALUES
    ('tienda_fisica', 'Venta en punto de venta físico (POS)'),
    ('web',           'Venta a través de la plataforma e-commerce'),
    ('app',           'Venta a través de la aplicación móvil')
ON CONFLICT DO NOTHING;
 
 
-- ------------------------------------------------------------
-- dim_tienda
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dw.dim_tienda (
    id_tienda       SERIAL          PRIMARY KEY,
    nombre_tienda   VARCHAR(150)    NOT NULL,
    ciudad          VARCHAR(100)    NOT NULL,
    region          VARCHAR(100)    NOT NULL DEFAULT 'Metropolitana'
);
 
COMMENT ON TABLE dw.dim_tienda               IS 'Dimensión de tiendas físicas — fuente: ERP / POS';
 
-- Tiendas presentes en los datasets
INSERT INTO dw.dim_tienda (nombre_tienda, ciudad, region) VALUES
    ('Santiago Centro',  'Santiago',    'Metropolitana'),
    ('Providencia',      'Providencia', 'Metropolitana'),
    ('Maipú',            'Maipú',       'Metropolitana'),
    ('Las Condes',       'Las Condes',  'Metropolitana'),
    ('La Florida',       'La Florida',  'Metropolitana'),
    ('Puente Alto',      'Puente Alto', 'Metropolitana'),
    ('Ñuñoa',            'Ñuñoa',       'Metropolitana'),
    ('Online',           'N/A',         'N/A')            -- canal online no tiene tienda física
ON CONFLICT DO NOTHING;
 
 
-- ============================================================
--  TABLA DE HECHOS
-- ============================================================
 
-- ------------------------------------------------------------
-- fact_ventas  (consolida ventas_pos + ventas_online)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dw.fact_ventas (
    id_venta            SERIAL          PRIMARY KEY,
 
    -- Claves foráneas a dimensiones
    id_tiempo_fk        INT             NOT NULL REFERENCES dw.dim_tiempo(id_tiempo),
    id_cliente_fk       INT             NOT NULL REFERENCES dw.dim_cliente(id_cliente),
    id_producto_fk      INT             NOT NULL REFERENCES dw.dim_producto(id_producto),
    id_canal_fk         INT             NOT NULL REFERENCES dw.dim_canal(id_canal),
    id_tienda_fk        INT                      REFERENCES dw.dim_tienda(id_tienda),
 
    -- Métricas
    cantidad            SMALLINT        NOT NULL DEFAULT 1,
    precio_unitario     NUMERIC(12,2)   NOT NULL,
    total_venta         NUMERIC(14,2)   NOT NULL,   -- cantidad * precio_unitario
 
    -- Trazabilidad
    fuente              VARCHAR(20)     NOT NULL,   -- POS | online
    id_origen           INT             NOT NULL    -- id_venta del POS o id_orden del e-commerce
);
 
COMMENT ON TABLE  dw.fact_ventas              IS 'Tabla de hechos de ventas — consolida POS y e-commerce';
COMMENT ON COLUMN dw.fact_ventas.fuente       IS 'POS | online — identifica el sistema de origen';
COMMENT ON COLUMN dw.fact_ventas.id_origen    IS 'ID original del registro en el sistema fuente';
COMMENT ON COLUMN dw.fact_ventas.id_tienda_fk IS 'NULL cuando el canal es web o app';
 
 
-- ============================================================
--  ÍNDICES — mejoran el rendimiento de las consultas analíticas
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_fv_tiempo   ON dw.fact_ventas(id_tiempo_fk);
CREATE INDEX IF NOT EXISTS idx_fv_cliente  ON dw.fact_ventas(id_cliente_fk);
CREATE INDEX IF NOT EXISTS idx_fv_producto ON dw.fact_ventas(id_producto_fk);
CREATE INDEX IF NOT EXISTS idx_fv_canal    ON dw.fact_ventas(id_canal_fk);
CREATE INDEX IF NOT EXISTS idx_fv_fuente   ON dw.fact_ventas(fuente);