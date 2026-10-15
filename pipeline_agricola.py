"""
Pipeline de Automatización de Datos Agrícolas de Precisión
==========================================================

Simula la ingesta, limpieza, análisis geoespacial y visualización
de datos de sensores de humedad y NDVI en un fundo agrícola ficticio.

Este módulo implementa un pipeline ETL (Extract, Transform, Load) que procesa
datos geoespaciales de sensores agrícolas para generar reportes de salud
vegetal y mapas temáticos.

Autor: Equipo de Ingeniería de Datos Geoespaciales
Versión: 2.0.0 (Production-Ready)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch
from shapely.geometry import Polygon

# ---------------------------------------------------------------------------
# Configuración del módulo
# ---------------------------------------------------------------------------

# Constantes de configuración globales
NUM_LOTES: int = 15
SEED: int = 42
CRS_GEOGRAFICO: str = "EPSG:4326"  # Coordenadas geográficas (grados decimales)
CRS_PROYECTADO: str = "EPSG:32719"  # Proyección UTM Zona 19S (metros)

# Generador de números pseudoaleatorios con semilla fija para reproducibilidad
rng = np.random.default_rng(SEED)

# ---------------------------------------------------------------------------
# Configuración de logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pipeline_agricola")


# ---------------------------------------------------------------------------
# Funciones del pipeline
# ---------------------------------------------------------------------------


def generar_datos_ficticios() -> gpd.GeoDataFrame:
    """Genera un GeoDataFrame simulando lotes agrícolas y datos de sensores.

    Crea datos sintéticos para ``NUM_LOTES`` parcelas agrícolas, incluyendo
    geometrías poligonales irregulares y variables de sensores como NDVI,
    humedad del suelo, humedad ambiental y temperatura. Se introducen
    deliberadamente valores nulos y anomalías para simular datos sucios.

    Returns:
        GeoDataFrame con ``NUM_LOTES`` filas, columnas de sensores y geometría
        poligonal en CRS geográfico (EPSG:4326).

    Raises:
        RuntimeError: Si no se pueden generar geometrías válidas.
    """
    logger.info("Iniciando generación de datos simulados.")

    geometries: list[Polygon] = []
    data: Dict[str, Any] = {
        "lote_id": [f"L{i:03d}" for i in range(1, NUM_LOTES + 1)],
        "campana": rng.choice(["Primavera", "Verano", "Otoño", "Invierno"], size=NUM_LOTES),
        "ndvi": np.round(rng.uniform(0.1, 0.95, size=NUM_LOTES), 2),
        "humedad_suelo": np.round(rng.uniform(5, 45, size=NUM_LOTES), 1),
        "humedad_amb": np.round(rng.uniform(20, 80, size=NUM_LOTES), 1),
        "temperatura": np.round(rng.uniform(15, 40, size=NUM_LOTES), 1),
    }

    # --- Generación de geometrías poligonales irregulares ---
    # Se crea un layout de lotes en filas de 5, avanzando en X e Y
    base_x, base_y = 0.0, 0.0
    for i in range(NUM_LOTES):
        # Coordenadas base del vértice inferior izquierdo del lote
        x = base_x + rng.uniform(2, 5)
        y = base_y + rng.uniform(2, 5)
        size = rng.uniform(4, 7)

        # Pequeña variación en los vértices superiores para irregularidad
        offset_top = rng.uniform(-0.3, 0.3)
        offset_right = rng.uniform(-0.3, 0.3)

        # Construcción del polígono (rectángulo ligeramente irregular)
        poly = Polygon([
            (x, y),
            (x + size, y),
            (x + size + offset_right, y + size),
            (x + offset_top, y + size),
        ])

        # Buffer(0) repara auto-intersecciones y devuelve geometría válida
        if not poly.is_valid:
            poly = poly.buffer(0)

        geometries.append(poly)

        # Avanzar al siguiente lote en X
        base_x = x + size + rng.uniform(2, 3)

        # Cada 5 lotes, saltar a una nueva fila en Y
        if (i + 1) % 5 == 0:
            base_x = 0
            base_y = y + size + rng.uniform(3, 5)

    data["geometry"] = geometries
    df = gpd.GeoDataFrame(data, crs=CRS_GEOGRAFICO)

    # Forzar geometrías válidas: buffer(0) repara auto-intersecciones
    df["geometry"] = df["geometry"].buffer(0)

    # Filtrar geometrías vacías o degeneradas que resulten del buffer
    df = df[df["geometry"].notna()].reset_index(drop=True)

    if df.empty:
        raise RuntimeError("No se generaron geometrías válidas. Revisar algoritmo de generación.")

    # --- Introducir datos sucios (nulos y anomalías) para simular sensores reales ---
    df.loc[3, "humedad_suelo"] = np.nan    # Sensor falló (nulo)
    df.loc[7, "ndvi"] = np.nan             # Sensor cayó fuera de línea
    df.loc[2, "temperatura"] = 999.0       # Valor imposible (anomalía)
    df.loc[5, "humedad_suelo"] = -5.0      # Valor negativo imposible (anomalía)

    logger.info("Generados %d lotes con %d columnas (incl. geometría).", len(df), len(df.columns))
    return df


def limpiar_y_procesar(df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Limpia datos sucios y calcula métricas agrícolas derivadas.

    Realiza las siguientes operaciones de transformación:
    1. Conversión de tipos numéricos con coerción de errores.
    2. Clasificación del estrés hídrico según humedad del suelo.
    3. Filtrado de valores atípicos fuera de rangos físicos válidos.
    4. Imputación de valores nulos con la mediana de cada variable.
    5. Cálculo del Índice de Salud Vegetal Combinado (SVC).
    6. Categorización del estado de salud por lote.

    Args:
        df: GeoDataFrame de lotes con datos de sensores (posiblemente sucios).

    Returns:
        GeoDataFrame con datos limpios y columnas derivadas añadidas.

    Raises:
        ValueError: Si el GeoDataFrame está vacío.
    """
    if df.empty:
        raise ValueError("El GeoDataFrame de entrada está vacío.")

    logger.info("Iniciando limpieza y procesamiento de datos.")
    df = df.copy()

    # --- 1. Conversión de tipos numéricos ---
    # errors="coerce" convierte valores no numéricos en NaN para posterior imputación
    df["ndvi"] = pd.to_numeric(df["ndvi"], errors="coerce")
    df["humedad_suelo"] = pd.to_numeric(df["humedad_suelo"], errors="coerce")
    df["humedad_amb"] = pd.to_numeric(df["humedad_amb"], errors="coerce")
    df["temperatura"] = pd.to_numeric(df["temperatura"], errors="coerce")

    # --- 2. Clasificación del estrés hídrico ---
    # humedad_ideal: valor de humedad de suelo considerado óptimo (25.0 %)
    # Clasificación basada en umbrales porcentuales del valor ideal:
    #   - Alto:        < 60 % del ideal  (humedad muy baja → planta en estrés severo)
    #   - Moderado:    60–85 % del ideal (humedad insuficiente → planta en estrés leve)
    #   - Bajo:        ≥ 85 % del ideal  (humedad adecuada → sin estrés hídrico)
    humedad_ideal: float = 25.0
    df["estr_s_hidr"] = df["humedad_suelo"].apply(
        lambda h: "Alto" if h < humedad_ideal * 0.6
        else ("Moderado" if h < humedad_ideal * 0.85 else "Bajo")
    )

    # --- 3. Filtrado de anomalías de sensores ---
    # Establecimiento de rangos físicos válidos para cada variable:
    #   - Temperatura:  > 50 °C es imposible en cultivos → NaN
    #   - Humedad suelo: < 0 % o > 60 % es físicamente imposible → NaN
    #   - NDVI: rango teórico [0, 1] → valores fuera → NaN
    df.loc[df["temperatura"] > 50, "temperatura"] = np.nan
    df.loc[df["humedad_suelo"] < 0, "humedad_suelo"] = np.nan
    df.loc[df["humedad_suelo"] > 60, "humedad_suelo"] = np.nan
    df.loc[(df["ndvi"] < 0) | (df["ndvi"] > 1), "ndvi"] = np.nan

    # --- 4. Imputación de valores nulos con la mediana ---
    # La mediana es robusta a valores atípicos y mantiene la distribución
    df["ndvi"] = df["ndvi"].fillna(df["ndvi"].median())
    df["humedad_suelo"] = df["humedad_suelo"].fillna(df["humedad_suelo"].median())
    df["humedad_amb"] = df["humedad_amb"].fillna(df["humedad_amb"].median())
    df["temperatura"] = df["temperatura"].fillna(df["temperatura"].median())

    # --- 5. Cálculo del Índice de Salud Vegetal Combinado (SVC) ---
    # Fórmula ponderada que combina tres indicadores:
    #   SVC = 0.5 × NDVI + 0.3 × (1 - estrés_hídrico) + 0.2 × (humedad_suelo / 50)
    #
    # Componentes:
    #   - NDVI (50 %):    Índice de Vegetación de Diferencia Normalizada, mide la
    #                     densidad de vegetación. Rango [0, 1]; valores > 0.7 son
    #                     excelentes, < 0.3 indican estrés.
    #   - Estrés hídrico (30 %): Inverso del estrés. "Alto" → 0.0 (máxima
    #                     penalización), "Bajo" → 1.0 (sin penalización).
    #                     Se resta del 1 para que menor estrés = mayor salud.
    #   - Humedad suelo (20 %): Normalizado entre 0 y 50 %, donde 50 % es el
    #                     máximo valor esperado. Más humedad = mejor salud.
    #
    # El resultado está en [0, 1]; valores cercanos a 1 indican salud óptima.
    df["salud_veg_comb"] = (
        0.5 * df["ndvi"]
        + 0.3 * (1 - df["estr_s_hidr"].map({"Alto": 1.0, "Moderado": 0.5, "Bajo": 0.0}))
        + 0.2 * (df["humedad_suelo"] / 50.0)
    ).round(3)

    # --- 6. Categorización del estado de salud ---
    # Clasifica cada lote en una categoría cualitativa basada en NDVI y estrés:
    #   - Saludable:   NDVI ≥ 0.7 y estrés bajo
    #   - Moderada:    NDVI ≥ 0.5 y estrés no alto
    #   - Estrés:      No cumple los criterios anteriores
    #   - Desconocida: NDVI nulo (no debería ocurrir tras imputación)
    def categorizar_salud(row: pd.Series) -> str:
        """Clasifica el estado de salud de un lote según reglas de negocio."""
        if pd.isna(row["ndvi"]):
            return "Desconocida"
        if row["ndvi"] >= 0.7 and row["estr_s_hidr"] == "Bajo":
            return "Saludable"
        if row["ndvi"] >= 0.5 and row["estr_s_hidr"] != "Alto":
            return "Moderada"
        return "Estrés"

    df["estado_salud"] = df.apply(categorizar_salud, axis=1)

    logger.info("Procesamiento completado. Valores nulos imputados, anomalías filtradas, métricas calculadas.")
    return df


def analizar_geoespacial(df: gpd.GeoDataFrame) -> Dict[str, Any]:
    """Agrupa y analiza lotes por zona geográfica y nivel de estrés hídrico.

    Asigna una zona (Norte/Sur) a cada lote basada en la posición Y del
    centroide representativo. El cálculo de centroides se realiza en un
    CRS proyectado (UTM) para garantizar distancias y áreas exactas.

    Args:
        df: GeoDataFrame procesado con columnas 'geometry', 'ndvi',
            'humedad_suelo', 'estr_s_hidr' y 'salud_veg_comb'.

    Returns:
        Diccionario con dos claves:
        - ``resumen_agrupado``: DataFrame agrupado por zona y estrés con
          métricas promedio.
        - ``df_procesado``: GeoDataFrame con la columna 'zona' añadida.

    Raises:
        RuntimeError: Si la re-proyección a EPSG:32719 falla.
        ValueError: Si el GeoDataFrame está vacío.
    """
    if df.empty:
        raise ValueError("El GeoDataFrame de entrada está vacío.")

    logger.info("Iniciando análisis geoespacial.")
    df = df.copy()

    # --- Re-proyección a CRS proyectado ---
    # Se requiere un CRS proyectado (EPSG:32719, UTM Zona 19S) porque:
    #   1. Las coordenadas geográficas (EPSG:4326) usan grados decimales,
    #      cuya unidad (ángulo) no corresponde a una distancia lineal.
    #   2. El cálculo de centroides y el uso de medianas requieren una
    #      unidad de medida consistente (metros en UTM).
    #   3. Las operaciones geométricas (buffer, área, distancia) son
    #      inexactas en CRS geográficos debido a la curvatura terrestre.
    #
    # EPSG:32719 cubre la zona sur de América del Sur (incluye Chile, Argentina,
    # Uruguay, parte de Brasil) y es adecuado para coordenadas en esa región.
    try:
        df_proj = df.to_crs(CRS_PROYECTADO)
        logger.info("Re-proyección a %s completada.", CRS_PROYECTADO)
    except Exception as e:
        raise RuntimeError(f"Error al re-proyectar a {CRS_PROYECTADO}: {e}") from e

    # --- Cálculo de centroides representativos ---
    # representative_point() garantiza un punto dentro del polígono incluso
    # si es concave, a diferencia de centroid() que puede caer fuera.
    centroides = df_proj.geometry.representative_point()

    # --- Asignación de zona (Norte/Sur) ---
    # Se usa la mediana de las coordenadas Y de los centroides como umbral.
    # Esto divide visualmente los lotes en dos grupos equitativos:
    #   - Norte: centroides con Y ≥ mediana
    #   - Sur:   centroides con Y <  mediana
    umbral_y = centroides.y.median()
    df["zona"] = np.where(centroides.y >= umbral_y, "Norte", "Sur")

    logger.info("Zona asignada: %d Norte, %d Sur.",
                (df["zona"] == "Norte").sum(), (df["zona"] == "Sur").sum())

    # --- Agrupación y resumen estadístico ---
    # Se agrupan los lotes por (zona, estrés hídrico) y se calculan
    # métricas promedio para generar un reporte resumido.
    resumen = (
        df.groupby(["zona", "estr_s_hidr"])
        .agg(
            num_lotes=("lote_id", "count"),
            ndvi_prom=("ndvi", "mean"),
            humedad_prom=("humedad_suelo", "mean"),
            salud_prom=("salud_veg_comb", "mean"),
        )
        .round(2)
    )

    logger.info("Análisis geoespacial completado. %d grupos de zona/estrés.", len(resumen))
    return {"resumen_agrupado": resumen, "df_procesado": df}


def visualizar(df: gpd.GeoDataFrame, output_path: str = "mapa_salud_vegetal.png") -> None:
    """Genera y guarda un mapa temático coloreando lotes por estado de salud.

    Crea una figura con lotes coloreados según su categoría de salud
    (Saludable=verde, Moderada=naranja, Estrés=rojo, Desconocida=gris),
    etiquetas de ID de lote y una leyenda.

    Args:
        df: GeoDataFrame con columna 'geometry' y 'estado_salud'.
        output_path: Ruta del archivo de imagen de salida (PNG).

    Raises:
        IOError: Si no se puede guardar el archivo de imagen.
    """
    logger.info("Generando mapa temático de salud vegetal.")

    colores: Dict[str, str] = {
        "Saludable": "#2ca02c",   # verde
        "Moderada": "#ff7f0e",    # naranja
        "Estrés": "#d62728",      # rojo
        "Desconocida": "#7f7f7f", # gris
    }

    fig, ax = plt.subplots(1, 1, figsize=(14, 9))
    handles: list[Patch] = []

    # Dibujar cada categoría de salud con su color correspondiente
    for estado, color in colores.items():
        subset = df[df["estado_salud"] == estado]
        if not subset.empty:
            subset.plot(ax=ax, color=color, edgecolor="black", linewidth=1.5, alpha=0.8)
            handles.append(Patch(facecolor=color, edgecolor="black", label=estado))

    # Etiquetas de IDs de lote en el centroide representativo de cada polígono
    for _, row in df.iterrows():
        cx, cy = row.geometry.representative_point().x, row.geometry.representative_point().y
        ax.annotate(
            row["lote_id"], xy=(cx, cy), fontsize=8,
            ha="center", va="center", color="white", fontweight="bold",
        )

    ax.set_title("Estado de Salud Vegetal por Lote Agrícola", fontsize=14, fontweight="bold")
    ax.set_xlabel("Longitud")
    ax.set_ylabel("Latitud")
    ax.legend(handles=handles, title="Estado de Salud", loc="upper left", framealpha=0.9)
    ax.set_axisbelow(True)
    ax.grid(True, linestyle="--", alpha=0.4)

    plt.tight_layout()

    try:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info("Mapa guardado en: %s", os.path.abspath(output_path))
    except Exception as e:
        raise IOError(f"Error al guardar el mapa en '{output_path}': {e}") from e
    finally:
        plt.close(fig)


def ejecutar_pipeline_agricola() -> None:
    """Ejecuta el pipeline completo de procesamiento agrícola.

    Orquesta las cuatro etapas del pipeline:
    1. Ingesta de datos simulados.
    2. Limpieza y procesamiento de datos.
    3. Análisis geoespacial.
    4. Visualización y generación de mapa temático.

    Cada etapa registra eventos de logging. Los errores se capturan y
    registran sin interrumpir el flujo del pipeline excepto en caso de
    fallos críticos.
    """
    logger.info("=" * 60)
    logger.info("PIPELINE DE DATOS AGRÍCOLAS DE PRECISIÓN")
    logger.info("=" * 60)

    # --- 1. INGESTA ---
    logger.info("[1] Ingesta de datos simulados...")
    try:
        df = generar_datos_ficticios()
        logger.info("    - %d lotes generados con %d columnas", len(df), len(df.columns))
    except Exception as e:
        logger.error("Falló la ingesta de datos: %s", e, exc_info=True)
        raise

    # --- 2. LIMPIEZA Y PROCESAMIENTO ---
    logger.info("[2] Limpieza y procesamiento de datos...")
    try:
        df_limpio = limpiar_y_procesar(df)
        logger.info("    - Valores nulos imputados")
        logger.info("    - Anomalías de sensores filtradas")
        logger.info("    - Índice de salud vegetal combinado calculado")
    except Exception as e:
        logger.error("Falló la limpieza de datos: %s", e, exc_info=True)
        raise

    # --- 3. ANÁLISIS GEOESPACIAL ---
    logger.info("[3] Análisis geoespacial...")
    try:
        resultado = analizar_geoespacial(df_limpio)
        df_procesado = resultado["df_procesado"]
        logger.info("\n    Resumen por zona y estrés hídrico:")
        # Se usa logging con formato de tabla para el resumen
        for linea in resultado["resumen_agrupado"].to_string().split("\n"):
            logger.info("    %s", linea)
    except Exception as e:
        logger.error("Falló el análisis geoespacial: %s", e, exc_info=True)
        raise

    # --- 4. VISUALIZACIÓN ---
    logger.info("[4] Visualización geoespacial...")
    try:
        visualizar(df_procesado)
        logger.info("    - Mapa generado y guardado en mapa_salud_vegetal.png")
    except Exception as e:
        logger.error("Falló la visualización: %s", e, exc_info=True)
        raise

    logger.info("Pipeline completado exitosamente.")


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ejecutar_pipeline_agricola()
