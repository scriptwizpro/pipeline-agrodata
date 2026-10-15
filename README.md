# Pipeline AgroData — Ingeniería de Datos Geoespaciales

<div align="center">

**Sistema de Procesamiento ETL para Agricultura de Precisión**

Automatización de la ingesta, limpieza, análisis y visualización de datos geoespaciales de sensores agrícolas.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-2CA55F?style=flat-square)](LICENSE)
[![GeoPandas](https://img.shields.io/badge/GeoPandas-1.0-319466?style=flat-square&logo=geopandas&logoColor=white)](https://geopandas.org/)

</div>

---

## 📋 Descripción

**Pipeline AgroData** es una solución de código abierto que simula un pipeline ETL (Extract, Transform, Load) para la gestión de datos de **Agricultura de Precisión**. Procesa datos geoespaciales de sensores remotos e in-situ —incluyendo NDVI, humedad del suelo, humedad ambiental y temperatura— para generar reportes de salud vegetal y mapas temáticos interactivos.

El pipeline está diseñado para fundos agrícolas que buscan optimizar recursos hídricos, detectar estrés vegetal temprano y soportar la toma de decisiones basada en datos geoespaciales.

---

## 🏗️ Arquitectura del Pipeline

```
┌─────────────────┐    ┌──────────────────┐    ┌────────────────────┐    ┌────────────────────┐
│   1. INGESTA    │    │  2. LIMPIEZA     │    │  3. ANÁLISIS       │    │  4. VISUALIZACIÓN  │
│   de Datos      │───▶│  y Procesamiento│───▶│  Geoespacial      │───▶│  y Reportes        │
│                 │    │                 │    │                   │    │                   │
│ • Generación    │    │ • Conversión    │    │ • Zonificación    │    │ • Mapa temático   │
│   de lotes con  │    │   de tipos      │    │   Norte/Sur       │    │   de salud        │
│   geometría     │    │ • Filtrado de   │    │ • Agrupación por  │    │ • Resumen estadísto│
│ • Simulación de │    │   anomalías     │    │   zona y estrés   │    │   por zona       │
│   sensores      │    │ • Imputación de │    │   hídrico         │    │ • Métricas KPI   │
│   sucios        │    │   nulos (mediana)│    │ • Métricas prome│    │                   │
└─────────────────┘    │ • Cálculo SVC   │    │   dias            │    └────────────────────┘
                       └──────────────────┘    └────────────────────┘
```

### 1. Fase de Ingesta (`generar_datos_ficticios`)

Simula la captura de datos de sensores IoT distribuidos en un fundo agrícola. Genera un `GeoDataFrame` con 15 lotes poligonales irregulares y datos de sensores. Se introducen deliberadamente valores nulos y anomalías para simular condiciones reales de campo.

### 2. Fase de Limpieza (`limpiar_y_procesar`)

Aplica transformaciones de calidad de datos:

| Operación | Descripción |
|-----------|-------------|
| Conversión de tipos | Coerción de valores no numéricos a `NaN` |
| Filtrado de anomalías | Rango físico válido: NDVI ∈ [0, 1], humedad ∈ [0, 60]% |
| Imputación | Mediana de cada variable para preservar distribución |
| Métrica SVC | Índice combinado de salud vegetal |

### 3. Fase Geoespacial (`analizar_geoespacial`)

- **CRS proyectado**: Re-proyección a UTM Zona 19S (EPSG:32719) para cálculos geométricos precisos.
- **Zonificación**: División Norte/Sur mediante la mediana de coordenadas Y de centroides.
- **Agrupación**: Resumen estadístico por zona y nivel de estrés hídrico.

### 4. Fase de Visualización (`visualizar`)

Genera un mapa temático coloreando los lotes según su estado de salud:

- 🟢 **Saludable** — Sin estrés, NDVI alto
- 🟧 **Moderada** — Estrés leve, NDVI intermedio
- 🔴 **Estrés** — Estrés severo, NDVI bajo
- ⬜ **Desconocida** — Datos insuficientes

---

## 📐 Indicadores Técnicos

### NDVI — Índice de Vegetación de Diferencia Normalizada

Medida espectral de la salud vegetal basada en la reflectancia infrarroja y visible.

| Rango | Interpretación |
|-------|----------------|
| 0.0 – 0.3 | Vegetación escasa / suelo desnudo |
| 0.3 – 0.6 | Vegetación moderada / en crecimiento |
| 0.6 – 0.9 | Vegetación densa / saludable |

### Estrés Hídrico

Clasificación basada en la humedad del suelo relativa al valor ideal (25%):

| Clase | Condición | Umbral |
|-------|-----------|--------|
| **Alto** | Humedad < 60% del ideal | < 15% |
| **Moderado** | Humedad 60–85% del ideal | 15–21.25% |
| **Bajo** | Humedad ≥ 85% del ideal | ≥ 21.25% |

### Índice de Salud Vegetal Combinado (SVC)

Fórmula ponderada que integra tres dimensiones de salud:

```
SVC = 0.5 × NDVI + 0.3 × (1 − Estres_Hidr) + 0.2 × (Humedad_suelo / 50)
```

| Peso | Componente | Justificación |
|------|-----------|---------------|
| 50% | NDVI | Métrica directa de biomasa y vigor fotosintético |
| 30% | Estrés hídrico | Inverso del estrés; la sequía es el factor limitante principal |
| 20% | Humedad del suelo | Contribución directa al desarrollo radicular y nutrición |

El resultado está normalizado en [0, 1], donde valores > 0.6 indican vigor óptimo.

---

## 🚀 Instalación

### Requisitos previos

- Python 3.10 o superior
- pip (gestor de paquetes)

### Instalación de dependencias

```bash
git clone https://github.com/usuario/pipeline-agrodata.git
cd pipeline-agrodata

python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

### Dependencias

| Librería | Versión | Propósito |
|----------|---------|-----------|
| numpy | ≥ 2.0 | Computación numérica y generación de datos |
| pandas | ≥ 2.2 | Manipulación de datos tabulares |
| geopandas | ≥ 1.0 | Procesamiento geoespacial y GeoDataFrames |
| shapely | ≥ 2.0 | Operaciones geométricas (Polygon, buffer, etc.) |
| pyproj | ≥ 3.6 | Transformaciones de sistemas de coordenadas |
| matplotlib | ≥ 3.9 | Visualización y generación de mapas |

---

## ▶️ Ejecución

```bash
python pipeline_agricola.py
```

### Salida esperada

El pipeline genera:

1. **Consola**: Registro de eventos con niveles de logging (INFO/WARNING/ERROR)
2. **Archivo**: `mapa_salud_vegetal.png` — mapa temático de salud vegetal
3. **Resumen**: Tabla de métricas promedio por zona y estrés hídrico

---

## 📁 Estructura del Repositorio

```
pipeline-agrodata/
├── pipeline_agricola.py    # Script principal del pipeline ETL
├── requirements.txt        # Dependencias con versiones
├── README.md               # Esta documentación
└── mapa_salud_vegetal.png  # Output generado (no incluido en el repo)
```

---

## 🛠️ Diseño Técnico

### Manejo de errores

- Cada etapa del pipeline está envuelta en bloques `try-except` con logging detallado.
- Los errores críticos (fallos de proyección, geometrías inválidas) se elevan como excepciones con contexto.
- El backend de matplotlib se fija a `Agg` para compatibilidad con entornos sin display.

### Reproducibilidad

- Semilla fija (`SEED = 42`) en el generador de números aleatorios.
- Tipado estricto (type hints) en todas las funciones públicas.
- CRS constante (`EPSG:4326` geográfico / `EPSG:32719` proyectado).

### Extensibilidad

El pipeline está modularizado por etapas, permitiendo:

- Sustituir la ingesta simulada por datos reales (API de sensores, archivos GeoJSON).
- Añadir nuevos indicadores agrícolas (NDRE, EVI, etc.).
- Integrar con bases de datos o servicios en la nube.

---

## 📄 Licencia

Este proyecto está bajo la licencia MIT. Ver el archivo [LICENSE](LICENSE) para más detalles.

---

<div align="center">

**Desarrollado con ❤️ por el Equipo de Ingeniería de Datos Geoespaciales**

</div>
