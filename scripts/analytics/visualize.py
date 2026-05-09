# ============================================================
#  RetailStart Chile S.A. — Data Platform
#  Archivo : scripts/analytics/visualize.py
#  Etapa   : Visualización — integrated/ → dashboards/exports/
# ============================================================
 
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from datetime import datetime
from dotenv import load_dotenv
 
load_dotenv()
 
# ------------------------------------------------------------
# Rutas base
# ------------------------------------------------------------
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INTEGRATED = os.path.join(BASE_DIR, "data", "processed", "integrated")
EXPORTS    = os.path.join(BASE_DIR, "dashboards", "exports")
 
# ------------------------------------------------------------
# Estilo global
# ------------------------------------------------------------
sns.set_theme(style="whitegrid", palette="muted")
COLORES = ["#534AB7", "#1D9E75", "#D85A30", "#EF9F27", "#378ADD", "#639922"]
 
 
def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
 
 
def guardar(fig, nombre: str):
    os.makedirs(EXPORTS, exist_ok=True)
    ruta = os.path.join(EXPORTS, nombre)
    fig.savefig(ruta, dpi=150, bbox_inches="tight")
    plt.close(fig)
    _log(f"  Guardado: {nombre}")
 
 
def formato_pesos(valor, pos):
    """Formatea eje Y en miles con signo $."""
    if valor >= 1_000_000:
        return f"${valor/1_000_000:.1f}M"
    elif valor >= 1_000:
        return f"${valor/1_000:.0f}K"
    return f"${valor:.0f}"
 
 
# ============================================================
#  GRÁFICO 1 — Mejores clientes por volumen de compra
# ============================================================
 
def grafico_mejores_clientes():
    _log(">> Generando gráfico: mejores clientes...")
    df = pd.read_csv(os.path.join(INTEGRATED, "metricas_clientes.csv"))
    df["cliente"] = df["nombre"] + " " + df["apellido"]
    df = df.head(10)
 
    fig, ax = plt.subplots(figsize=(10, 6))
 
    barras = ax.barh(
        df["cliente"][::-1],
        df["total_compras"][::-1],
        color=COLORES[0],
        edgecolor="white",
        linewidth=0.5
    )
 
    # Etiquetas de valor
    for bar in barras:
        ancho = bar.get_width()
        ax.text(
            ancho + 5000, bar.get_y() + bar.get_height() / 2,
            formato_pesos(ancho, None),
            va="center", ha="left", fontsize=9, color="#444441"
        )
 
    # Colorear por segmento
    segmentos = df["segmento"][::-1].values
    colores_seg = {"Premium": "#534AB7", "Regular": "#1D9E75", "Nuevo": "#EF9F27"}
    for bar, seg in zip(barras, segmentos):
        bar.set_color(colores_seg.get(seg, COLORES[0]))
 
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(formato_pesos))
    ax.set_xlabel("Total compras (CLP)", fontsize=11)
    ax.set_title("¿Quiénes son los mejores clientes?", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlim(0, df["total_compras"].max() * 1.25)
 
    # Leyenda segmentos
    from matplotlib.patches import Patch
    leyenda = [Patch(color=c, label=s) for s, c in colores_seg.items()]
    ax.legend(handles=leyenda, title="Segmento", loc="lower right", fontsize=9)
 
    fig.tight_layout()
    guardar(fig, "01_mejores_clientes.png")
 
 
# ============================================================
#  GRÁFICO 2 — Ventas por canal
# ============================================================
 
def grafico_ventas_por_canal():
    _log(">> Generando gráfico: ventas por canal...")
    df = pd.read_csv(os.path.join(INTEGRATED, "metricas_canal.csv"))
 
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
 
    # Pie chart
    wedges, texts, autotexts = ax1.pie(
        df["total_ventas"],
        labels=df["canal"],
        autopct="%1.1f%%",
        colors=COLORES[:len(df)],
        startangle=90,
        wedgeprops={"edgecolor": "white", "linewidth": 2}
    )
    for at in autotexts:
        at.set_fontsize(10)
        at.set_fontweight("bold")
    ax1.set_title("Distribución por canal", fontsize=12, fontweight="bold")
 
    # Barras
    barras = ax2.bar(
        df["canal"],
        df["total_ventas"],
        color=COLORES[:len(df)],
        edgecolor="white",
        linewidth=0.5,
        width=0.5
    )
    for bar in barras:
        alto = bar.get_height()
        ax2.text(
            bar.get_x() + bar.get_width() / 2, alto + 5000,
            formato_pesos(alto, None),
            ha="center", va="bottom", fontsize=9, color="#444441"
        )
 
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(formato_pesos))
    ax2.set_xlabel("Canal de venta", fontsize=11)
    ax2.set_ylabel("Total ventas (CLP)", fontsize=11)
    ax2.set_title("¿Qué canal vende más?", fontsize=12, fontweight="bold")
    ax2.set_ylim(0, df["total_ventas"].max() * 1.2)
 
    fig.suptitle("Análisis de Ventas por Canal — RetailStart Chile",
                 fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    guardar(fig, "02_ventas_por_canal.png")
 
 
# ============================================================
#  GRÁFICO 3 — Productos más vendidos
# ============================================================
 
def grafico_productos_mas_vendidos():
    _log(">> Generando gráfico: productos más vendidos...")
    df = pd.read_csv(os.path.join(INTEGRATED, "metricas_producto.csv"))
 
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
 
    # Por total de ventas
    df_ventas = df.sort_values("total_ventas", ascending=True)
    colores_cat = {
        "Tecnologia": COLORES[0],
        "Vestuario":  COLORES[1],
        "Hogar":      COLORES[2]
    }
    colores_barras = [colores_cat.get(c, COLORES[3]) for c in df_ventas["categoria"]]
 
    barras1 = ax1.barh(
        df_ventas["nombre_producto"],
        df_ventas["total_ventas"],
        color=colores_barras,
        edgecolor="white",
        linewidth=0.5
    )
    for bar in barras1:
        ancho = bar.get_width()
        ax1.text(
            ancho + 3000, bar.get_y() + bar.get_height() / 2,
            formato_pesos(ancho, None),
            va="center", ha="left", fontsize=9, color="#444441"
        )
    ax1.xaxis.set_major_formatter(mticker.FuncFormatter(formato_pesos))
    ax1.set_title("Por total vendido (CLP)", fontsize=12, fontweight="bold")
    ax1.set_xlim(0, df_ventas["total_ventas"].max() * 1.3)
 
    # Por unidades vendidas
    df_unidades = df.sort_values("unidades", ascending=True)
    barras2 = ax2.barh(
        df_unidades["nombre_producto"],
        df_unidades["unidades"],
        color=COLORES[4],
        edgecolor="white",
        linewidth=0.5
    )
    for bar in barras2:
        ancho = bar.get_width()
        ax2.text(
            ancho + 0.05, bar.get_y() + bar.get_height() / 2,
            f"{int(ancho)} uds.",
            va="center", ha="left", fontsize=9, color="#444441"
        )
    ax2.set_title("Por unidades vendidas", fontsize=12, fontweight="bold")
    ax2.set_xlim(0, df_unidades["unidades"].max() * 1.3)
 
    # Leyenda categorías
    from matplotlib.patches import Patch
    leyenda = [Patch(color=c, label=s) for s, c in colores_cat.items()]
    ax1.legend(handles=leyenda, title="Categoría", loc="lower right", fontsize=9)
 
    fig.suptitle("¿Qué productos tienen más ventas? — RetailStart Chile",
                 fontsize=14, fontweight="bold")
    fig.tight_layout()
    guardar(fig, "03_productos_mas_vendidos.png")
 
 
# ============================================================
#  GRÁFICO 4 — Ventas por categoría
# ============================================================
 
def grafico_ventas_por_categoria():
    _log(">> Generando gráfico: ventas por categoría...")
    df = pd.read_csv(os.path.join(INTEGRATED, "metricas_categoria.csv"))
 
    fig, ax = plt.subplots(figsize=(8, 5))
 
    barras = ax.bar(
        df["categoria"],
        df["total_ventas"],
        color=COLORES[:len(df)],
        edgecolor="white",
        linewidth=0.5,
        width=0.5
    )
    for bar in barras:
        alto = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2, alto + 3000,
            formato_pesos(alto, None),
            ha="center", va="bottom", fontsize=10, color="#444441"
        )
 
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(formato_pesos))
    ax.set_xlabel("Categoría", fontsize=11)
    ax.set_ylabel("Total ventas (CLP)", fontsize=11)
    ax.set_title("Ventas por categoría de producto", fontsize=14, fontweight="bold", pad=15)
    ax.set_ylim(0, df["total_ventas"].max() * 1.2)
 
    fig.tight_layout()
    guardar(fig, "04_ventas_por_categoria.png")
 
 
# ============================================================
#  GRÁFICO 5 — Evolución de ventas por fecha
# ============================================================
 
def grafico_evolucion_ventas():
    _log(">> Generando gráfico: evolución de ventas...")
    df = pd.read_csv(os.path.join(INTEGRATED, "metricas_fecha.csv"))
    df["fecha"] = pd.to_datetime(df["fecha"])
 
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
 
    # Total ventas
    ax1.plot(df["fecha"], df["total_ventas"],
             color=COLORES[0], linewidth=2.5, marker="o", markersize=6)
    ax1.fill_between(df["fecha"], df["total_ventas"],
                     alpha=0.15, color=COLORES[0])
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(formato_pesos))
    ax1.set_ylabel("Total ventas (CLP)", fontsize=11)
    ax1.set_title("Evolución diaria de ventas — RetailStart Chile",
                  fontsize=14, fontweight="bold")
 
    # Número de transacciones
    ax2.bar(df["fecha"], df["transacciones"],
            color=COLORES[1], edgecolor="white", linewidth=0.5, width=0.6)
    ax2.set_ylabel("N° transacciones", fontsize=11)
    ax2.set_xlabel("Fecha", fontsize=11)
 
    fig.tight_layout()
    guardar(fig, "05_evolucion_ventas.png")
 
 
# ============================================================
#  FUNCIÓN PRINCIPAL
# ============================================================
 
def run():
    _log("=" * 50)
    _log("INICIO GENERACIÓN DE VISUALIZACIONES")
    _log("=" * 50)
 
    grafico_mejores_clientes()
    grafico_ventas_por_canal()
    grafico_productos_mas_vendidos()
    grafico_ventas_por_categoria()
    grafico_evolucion_ventas()
 
    _log("")
    _log("=" * 50)
    _log(f"VISUALIZACIONES COMPLETAS — guardadas en dashboards/exports/")
    _log("=" * 50)
 
 
# ============================================================
#  Ejecución directa
# ============================================================
if __name__ == "__main__":
    run()