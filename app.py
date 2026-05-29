"""App principal de Streamlit para pricing dinámico, elasticidad y proyección de ventas.

Versión optimizada:
- Solo se renderiza una vista a la vez.
- La vista 1 solo limpia/cruza/calcula calidad.
- La elasticidad se calcula únicamente desde la vista 2.
- Pricing dinámico se calcula únicamente desde la vista 3.
- La base cruzada con NSE es la base maestra para elasticidad y pricing.
- Pricing depende explícitamente de la elasticidad SKU × trimestre calculada en la vista 2.
- Los cálculos pesados se guardan en caché de sesión y las lecturas/gráficas usan st.cache_data para evitar recálculos innecesarios.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.config import (
    COLUMNAS_LECTURA_NSE,
    COLUMNAS_LECTURA_PROMOCIONES,
    COLUMNAS_LECTURA_VENTAS,
    COLUMNAS_MINIMAS_VENTAS,
    ESCENARIOS_PRICING,
    LEER_SOLO_COLUMNAS_NECESARIAS,
    MAX_ROWS_PREVIEW,
    MAX_SKUS_CURVA_ELASTICIDAD,
)
from modules.utils import (
    build_default_nse,
    clean_sales_data,
    convert_df_to_csv,
    filter_dataframe_dependently,
    format_money,
    format_num,
    get_uploaded_file_info,
    get_uploaded_file_signature,
    merge_sales_with_nse,
    read_uploaded_file,
    render_kpi_card,
    validate_columns,
)


st.set_page_config(
    page_title="Pricing dinámico retail",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


CUSTOM_CSS = """
<style>
    .main .block-container {padding-top: 1.4rem;}
    .kpi-card {
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 18px 18px;
        background: #ffffff;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        min-height: 112px;
    }
    .kpi-title {
        color: #4b5563;
        font-size: 0.88rem;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .kpi-value {
        color: #111827;
        font-size: 1.65rem;
        font-weight: 800;
        line-height: 1.15;
    }
    .kpi-subtitle {
        color: #6b7280;
        font-size: 0.78rem;
        margin-top: 8px;
    }
    .section-card {
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 18px;
        background: #f9fafb;
        margin-bottom: 16px;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# =========================================================
# Caché de cálculos pesados
# =========================================================

def process_quality_cached(
    sales_df: pd.DataFrame,
    nse_df: pd.DataFrame | None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict, pd.DataFrame, pd.DataFrame, dict]:
    """
    Limpia ventas, cruza NSE y calcula semáforo de calidad.

    Esta función NO calcula elasticidad ni pricing. Así la app responde rápido
    después de cargar ventas y solo calcula la vista activa.
    """
    from modules.quality import calculate_quality_diagnosis

    ventas_limpias, resumen_limpieza, summary = clean_sales_data(sales_df)
    ventas_nse, nse_info = merge_sales_with_nse(ventas_limpias, nse_df)
    semaforo, calidad_varianza = calculate_quality_diagnosis(ventas_nse, resumen_limpieza, summary)
    return ventas_nse, resumen_limpieza, summary, semaforo, calidad_varianza, nse_info


def calculate_elasticity_cached(
    ventas_nse: pd.DataFrame,
    promo_df: pd.DataFrame | None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """
    Calcula elasticidad con caché.

    Se ejecuta solo desde la vista 2 o cuando la vista 3 necesita elasticidad.
    """
    from modules.elasticity import calculate_elasticity

    return calculate_elasticity(ventas_nse, promo_df)


def simulate_pricing_cached(
    ventas_base_elasticidad: pd.DataFrame,
    elasticidad: pd.DataFrame,
    bloques: list[dict],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Simula escenarios de pricing con caché.

    Se ejecuta solo desde la vista 3.
    """
    from modules.pricing import simulate_pricing_scenarios

    return simulate_pricing_scenarios(ventas_base_elasticidad, elasticidad, bloques)


@st.cache_data(show_spinner=False, max_entries=10)
def build_elasticity_curve_data(
    curva_df: pd.DataFrame,
    min_price: float,
    max_price: float,
    max_skus: int,
) -> pd.DataFrame:
    """Construye datos para la curva de elasticidad usando caché."""
    import numpy as np

    if curva_df is None or curva_df.empty:
        return pd.DataFrame()

    precios = np.linspace(max(0.01, float(min_price)), max(0.02, float(max_price)), 60)
    curva_rows = []
    for _, row in curva_df.head(max_skus).iterrows():
        alfa = row.get("Alfa")
        beta = row.get("Elasticidad")
        sku = row.get("SKU")
        trimestre = row.get("trimestre")
        if pd.isna(alfa) or pd.isna(beta):
            continue
        for precio in precios:
            demanda = np.exp(alfa + beta * np.log(precio))
            if np.isfinite(demanda):
                curva_rows.append(
                    {
                        "SKU": sku,
                        "Precio": precio,
                        "Demanda estimada": demanda,
                        "trimestre": trimestre,
                    }
                )
    return pd.DataFrame(curva_rows)


@st.cache_data(show_spinner=False, max_entries=10)
def aggregate_weekly_demand(ventas_f: pd.DataFrame) -> pd.DataFrame:
    """Agrega demanda semanal con caché para la vista de elasticidad."""
    if ventas_f is None or ventas_f.empty:
        return pd.DataFrame()

    if "tiene_promocion" in ventas_f.columns and ventas_f["tiene_promocion"].sum() > 0:
        serie = (
            ventas_f.groupby([pd.Grouper(key="tran_date", freq="W"), "tiene_promocion"], as_index=False)
            .agg(Demanda=("qty", "sum"))
        )
        serie["Promoción"] = serie["tiene_promocion"].map({1: "Con promoción", 0: "Sin promoción"}).fillna("Sin promoción")
        return serie

    return ventas_f.groupby(pd.Grouper(key="tran_date", freq="W"), as_index=False).agg(Demanda=("qty", "sum"))


@st.cache_data(show_spinner=False, max_entries=10)
def aggregate_pricing_chart_data(selected: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Agrega tablas para las tres gráficas de pricing con caché."""
    if selected is None or selected.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    money_group = (
        selected.groupby("trimestre", as_index=False)
        .agg(Ventas_normales=("Ingreso_Base", "sum"), Ventas_simuladas=("Ingreso_Simulado", "sum"))
    )
    money_long = money_group.melt(
        id_vars="trimestre",
        value_vars=["Ventas_normales", "Ventas_simuladas"],
        var_name="Serie",
        value_name="Ventas",
    )

    qty_group = (
        selected.groupby("trimestre", as_index=False)
        .agg(Cantidad_normal=("Unidades_Base", "sum"), Cantidad_simulada=("Unidades_Simuladas", "sum"))
    )
    qty_long = qty_group.melt(
        id_vars="trimestre",
        value_vars=["Cantidad_normal", "Cantidad_simulada"],
        var_name="Serie",
        value_name="Unidades",
    )

    im_group = (
        selected.groupby("trimestre", as_index=False)
        .agg(Ingreso_simulado=("Ingreso_Simulado", "sum"), Margen_simulado=("Margen_Simulado", "sum"))
    )
    im_long = im_group.melt(
        id_vars="trimestre",
        value_vars=["Ingreso_simulado", "Margen_simulado"],
        var_name="Métrica",
        value_name="Monto",
    )

    return money_long, qty_long, im_long


def _safe_sorted_options(df: pd.DataFrame, col: str | None) -> list[str]:
    """Devuelve opciones limpias y ordenadas para filtros dependientes."""
    if df is None or df.empty or col is None or col not in df.columns:
        return []
    values = (
        df[col]
        .dropna()
        .astype(str)
        .map(str.strip)
    )
    values = values[values != ""]
    return sorted(values.unique().tolist())


def _filter_fast(df: pd.DataFrame, col: str | None, value: object) -> pd.DataFrame:
    """Filtro ligero para cascadas de Streamlit sin copiar todo el DataFrame si no hace falta."""
    if df is None or df.empty or col is None or col not in df.columns or value in [None, "Todos", "Todas"]:
        return df
    return df.loc[df[col].astype(str) == str(value)]


def _dependent_selectbox(
    label: str,
    options: list[str],
    key: str,
    default: str,
    container,
) -> str:
    """Selectbox que se resetea si una selección previa ya no existe por filtros anteriores."""
    if not options:
        options = [default]
    if default not in options:
        options = [default] + options
    if st.session_state.get(key) not in options:
        st.session_state[key] = default
    with container:
        return st.selectbox(label, options, key=key)


def _df_to_excel_friendly_csv_bytes(df: pd.DataFrame, sep: str = ";") -> bytes:
    """CSV compatible con Excel en configuración regional de México/España.

    Usa UTF-8 con BOM y separador `;` para que Excel abra columnas correctamente.
    """
    if df is None or df.empty:
        return b""
    clean = df.copy()
    return clean.to_csv(index=False, sep=sep, encoding="utf-8-sig", lineterminator="\n").encode("utf-8-sig")


def _dataframes_to_zip_csv_bytes(files: dict[str, pd.DataFrame], sep: str = ";") -> bytes:
    """Empaqueta uno o varios DataFrames como CSV dentro de un ZIP en memoria."""
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename, df in files.items():
            csv_bytes = _df_to_excel_friendly_csv_bytes(df, sep=sep)
            zf.writestr(filename, csv_bytes)
    buffer.seek(0)
    return buffer.getvalue()


# =========================================================
# Estado de la app
# =========================================================

def init_state() -> None:
    """Inicializa session_state."""
    defaults = {
        "active_nse_df": build_default_nse(),
        "nse_source": "Base NSE predeterminada",
        "processed": False,
        "elasticity_ready": False,
        "pricing_ready": False,
        "ventas_limpias": pd.DataFrame(),
        "ventas_nse": pd.DataFrame(),
        "promo_df": None,
        "elasticidad": pd.DataFrame(),
        "ventas_base_elasticidad": pd.DataFrame(),
        "ventas_base_pricing": pd.DataFrame(),
        "bloques": [],
        "base_pricing": pd.DataFrame(),
        "simulacion": pd.DataFrame(),
        "resumen_pricing": pd.DataFrame(),
        "semaforo": pd.DataFrame(),
        "calidad_varianza": pd.DataFrame(),
        "resumen_limpieza": pd.DataFrame(),
        "nse_info": {},
        "sales_signature": None,
        "promo_signature": None,
        "nse_signature": "default_nse",
        "quality_cache_key": None,
        "elasticity_cache_key": None,
        "pricing_cache_key": None,
        "manual_cache": {"quality": {}, "elasticity": {}, "pricing": {}},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_model_results() -> None:
    """Limpia resultados derivados cuando cambia la base de ventas o NSE."""
    st.session_state.elasticity_ready = False
    st.session_state.pricing_ready = False
    st.session_state.elasticidad = pd.DataFrame()
    st.session_state.ventas_base_elasticidad = pd.DataFrame()
    st.session_state.bloques = []
    st.session_state.base_pricing = pd.DataFrame()
    st.session_state.simulacion = pd.DataFrame()
    st.session_state.resumen_pricing = pd.DataFrame()


def render_sidebar() -> str:
    """Renderiza sidebar. La lectura real ocurre solo con botones explícitos."""
    st.sidebar.title("📊 Pricing dinámico")
    st.sidebar.caption("Carga tus bases y navega entre vistas. Solo se ejecuta la vista activa.")

    vista = st.sidebar.radio(
        "Vista",
        [
            "1. Carga y diagnóstico de datos",
            "2. Elasticidad",
            "3. Pricing dinámico + proyección de ventas",
        ],
    )

    st.sidebar.divider()
    st.sidebar.subheader("Archivos")

    with st.sidebar.expander("A. Base de ventas obligatoria", expanded=True):
        st.info(
            "Sube CSV, Excel o Parquet con ventas. Columnas mínimas: "
            "`tran_date`, `qty`, `net_sale`, `prod_nbr`, `costo2`."
        )
        sales_file = st.file_uploader(
            "Base de ventas",
            type=["csv", "xlsx", "xls", "parquet"],
            key="sales_file",
        )

    with st.sidebar.expander("B. Base de promociones opcional", expanded=False):
        st.info(
            "Opcional. Si no se carga, la app funciona sin promociones. "
            "Se lee solo al presionar `Procesar / actualizar datos`."
        )
        promo_file = st.file_uploader(
            "Base de promociones",
            type=["csv", "xlsx", "xls", "parquet"],
            key="promo_file",
        )

    with st.sidebar.expander("C. Base NSE", expanded=False):
        st.info(
            "Puedes usar la base NSE predeterminada o subir una modificada. "
            "El modelo final usa `categoria_est_socio`, no `est_socio_nbr`."
        )

        default_nse = build_default_nse()
        st.download_button(
            "Descargar base NSE predeterminada",
            data=convert_df_to_csv(default_nse),
            file_name="base_nse_predeterminada.csv",
            mime="text/csv",
        )

        nse_file = st.file_uploader(
            "Subir base NSE modificada",
            type=["csv", "xlsx", "xls", "parquet"],
            key="nse_file",
        )

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Aplicar cambios de NSE", use_container_width=True):
                if nse_file is None:
                    st.warning("Primero sube una base NSE modificada.")
                else:
                    try:
                        columnas_nse = COLUMNAS_LECTURA_NSE if LEER_SOLO_COLUMNAS_NECESARIAS else None
                        st.session_state.active_nse_df = read_uploaded_file(nse_file, usecols=columnas_nse)
                        st.session_state.nse_signature = get_uploaded_file_signature(nse_file)
                        st.session_state.nse_source = f"Base NSE subida: {nse_file.name}"
                        st.success("Cambios de NSE aplicados. Vuelve a procesar ventas para reflejarlos.")
                        reset_model_results()
                        st.session_state.processed = False
                    except Exception as exc:
                        st.error(str(exc))
        with col_b:
            if st.button("Continuar con base predeterminada", use_container_width=True):
                st.session_state.active_nse_df = default_nse
                st.session_state.nse_signature = "default_nse"
                st.session_state.nse_source = "Base NSE predeterminada"
                st.success("Se usará la base predeterminada. Vuelve a procesar ventas para reflejarlo.")
                reset_model_results()
                st.session_state.processed = False

        st.caption(f"NSE activo: {st.session_state.nse_source}")

    if sales_file is not None:
        st.sidebar.success(f"Ventas listas: {get_uploaded_file_info(sales_file)}")
    if promo_file is not None:
        st.sidebar.success(f"Promociones listas: {get_uploaded_file_info(promo_file)}")

    process = st.sidebar.button("Procesar / actualizar datos", type="primary", use_container_width=True)
    if st.sidebar.button("Limpiar caché de esta sesión", use_container_width=True):
        st.cache_data.clear()
        st.session_state.manual_cache = {"quality": {}, "elasticity": {}, "pricing": {}}
        st.session_state.processed = False
        reset_model_results()
        st.sidebar.success("Caché limpiado. Vuelve a procesar la base si lo necesitas.")

    if process:
        if sales_file is None:
            st.sidebar.error("Primero sube la base de ventas.")
        else:
            try:
                columnas_ventas = COLUMNAS_LECTURA_VENTAS if LEER_SOLO_COLUMNAS_NECESARIAS else None
                columnas_promos = COLUMNAS_LECTURA_PROMOCIONES if LEER_SOLO_COLUMNAS_NECESARIAS else None

                with st.spinner("Leyendo archivo de ventas y preparando vista de calidad..."):
                    sales_signature = get_uploaded_file_signature(sales_file)
                    promo_signature = get_uploaded_file_signature(promo_file) if promo_file is not None else "sin_promociones"
                    nse_signature = st.session_state.get("nse_signature", "default_nse")
                    sales_df = read_uploaded_file(sales_file, usecols=columnas_ventas)
                    promo_df = read_uploaded_file(promo_file, usecols=columnas_promos) if promo_file is not None else None

                st.session_state.sales_signature = sales_signature
                st.session_state.promo_signature = promo_signature
                process_quality_pipeline(
                    sales_df,
                    promo_df,
                    st.session_state.active_nse_df,
                    cache_key=(sales_signature, nse_signature),
                )
            except Exception as exc:
                st.session_state.processed = False
                st.sidebar.error(str(exc))

    return vista


def process_quality_pipeline(
    sales_df: pd.DataFrame,
    promo_df: pd.DataFrame | None,
    nse_df: pd.DataFrame | None,
    cache_key: tuple | None = None,
) -> None:
    """Ejecuta solo limpieza, cruce NSE y semáforo."""
    if sales_df is None or sales_df.empty:
        st.sidebar.error("La base de ventas está vacía o no se pudo leer.")
        return

    missing = validate_columns(sales_df, COLUMNAS_MINIMAS_VENTAS)
    if missing:
        st.sidebar.error("Faltan columnas obligatorias: " + ", ".join(missing))
        st.session_state.processed = False
        return

    try:
        cache_key = cache_key or (st.session_state.get("sales_signature"), st.session_state.get("nse_signature"))
        cache = st.session_state.manual_cache.setdefault("quality", {})

        if cache_key in cache:
            ventas_nse, resumen_limpieza, summary, semaforo, calidad_varianza, nse_info = cache[cache_key]
        else:
            with st.spinner("Limpiando ventas, cruzando NSE y calculando calidad..."):
                ventas_nse, resumen_limpieza, summary, semaforo, calidad_varianza, nse_info = process_quality_cached(
                    sales_df,
                    nse_df,
                )
            cache.clear()
            cache[cache_key] = (ventas_nse, resumen_limpieza, summary, semaforo, calidad_varianza, nse_info)

        st.session_state.quality_cache_key = cache_key

        # Base maestra del análisis:
        # ventas_nse = ventas limpias + cruce NSE.
        # Esta misma base se usa tanto para elasticidad como para pricing.
        st.session_state.ventas_nse = ventas_nse
        st.session_state.ventas_limpias = ventas_nse  # alias para compatibilidad visual
        st.session_state.ventas_base_elasticidad = ventas_nse
        st.session_state.ventas_base_pricing = ventas_nse

        st.session_state.promo_df = promo_df
        st.session_state.resumen_limpieza = resumen_limpieza
        st.session_state.semaforo = semaforo
        st.session_state.calidad_varianza = calidad_varianza
        st.session_state.nse_info = nse_info
        st.session_state.processed = True
        reset_model_results()
        # reset_model_results limpia derivados; se restaura la base maestra.
        st.session_state.ventas_base_elasticidad = ventas_nse
        st.session_state.ventas_base_pricing = ventas_nse
        st.sidebar.success("Base limpia y cruzada con NSE. Elasticidad y pricing se calcularán solo en sus vistas.")

    except Exception as exc:
        st.session_state.processed = False
        st.sidebar.error(f"No se pudo procesar la base: {exc}")


def ensure_elasticity_ready(show_button: bool = True) -> bool:
    """Calcula elasticidad SKU × trimestre usando la base limpia y cruzada con NSE."""
    if not st.session_state.processed:
        return False

    if st.session_state.get("ventas_nse") is None or st.session_state.ventas_nse.empty:
        st.warning(
            "Primero procesa la base en la vista 1. La elasticidad necesita la base limpia y cruzada con NSE."
        )
        return False

    button_clicked = False
    if show_button:
        col_a, col_b = st.columns([1, 2])
        with col_a:
            button_clicked = st.button(
                "Calcular / actualizar elasticidad",
                type="primary" if not st.session_state.elasticity_ready else "secondary",
                use_container_width=True,
            )
        with col_b:
            st.caption(
                "Este cálculo se hace una sola vez por base gracias al caché de sesión. "
                "Cambiar filtros no recalcula el modelo."
            )

    if st.session_state.elasticity_ready and not button_clicked:
        return True

    if show_button and not button_clicked and not st.session_state.elasticity_ready:
        st.info("Presiona **Calcular / actualizar elasticidad** para ejecutar esta vista.")
        return False

    try:
        cache_key = (
            st.session_state.get("sales_signature"),
            st.session_state.get("nse_signature"),
            st.session_state.get("promo_signature"),
        )
        cache = st.session_state.manual_cache.setdefault("elasticity", {})
        if cache_key in cache:
            elasticidad, ventas_base_elasticidad, bloques = cache[cache_key]
        else:
            with st.spinner("Calculando elasticidad SKU × trimestre usando base cruzada con NSE..."):
                elasticidad, ventas_base_elasticidad, bloques = calculate_elasticity_cached(
                    st.session_state.ventas_nse,
                    st.session_state.promo_df,
                )
            cache.clear()
            cache[cache_key] = (elasticidad, ventas_base_elasticidad, bloques)

        st.session_state.elasticity_cache_key = cache_key
        st.session_state.elasticidad = elasticidad
        st.session_state.ventas_base_elasticidad = ventas_base_elasticidad
        st.session_state.bloques = bloques
        st.session_state.elasticity_ready = True
        st.session_state.pricing_ready = False
        st.success("Elasticidad calculada correctamente. Cambiar filtros no volverá a calcularla.")
        return True
    except Exception as exc:
        st.session_state.elasticity_ready = False
        st.error(f"No se pudo calcular elasticidad: {exc}")
        return False


def ensure_pricing_ready() -> bool:
    """Calcula pricing solo si ya existe elasticidad SKU × trimestre de la misma base NSE.

    Dependencias obligatorias:
    1. Vista 1 debe generar ventas_nse = ventas limpias + cruce NSE.
    2. Vista 2 debe calcular elasticidad SKU × trimestre sobre ventas_nse.
    3. Vista 3 usa ventas_nse + elasticidad; no recalcula elasticidad automáticamente.
    """
    if not st.session_state.processed:
        return False

    if st.session_state.get("ventas_nse") is None or st.session_state.ventas_nse.empty:
        st.warning(
            "Primero procesa la base en la vista **1. Carga y diagnóstico de datos**. "
            "Pricing necesita la base limpia y cruzada con NSE."
        )
        return False

    required_cols_pricing = ["prod_nbr", "tran_date", "qty", "net_sale", "categoria_est_socio"]
    missing_cols = [col for col in required_cols_pricing if col not in st.session_state.ventas_nse.columns]
    if missing_cols:
        st.error(
            "La base limpia y cruzada con NSE no tiene las columnas necesarias para pricing: "
            + ", ".join(missing_cols)
        )
        return False

    analysis_key = (
        st.session_state.get("sales_signature"),
        st.session_state.get("nse_signature"),
        st.session_state.get("promo_signature"),
    )

    if (
        not st.session_state.get("elasticity_ready", False)
        or st.session_state.elasticidad is None
        or st.session_state.elasticidad.empty
    ):
        st.warning(
            "Primero calcula la elasticidad en la vista **2. Elasticidad**. "
            "La vista de pricing depende de la elasticidad por SKU y trimestre."
        )
        return False

    if st.session_state.get("elasticity_cache_key") != analysis_key:
        st.warning(
            "La elasticidad guardada no corresponde a la base actual de ventas + NSE + promociones. "
            "Vuelve a calcular elasticidad en la vista **2. Elasticidad** antes de calcular pricing."
        )
        st.session_state.pricing_ready = False
        return False

    col_a, col_b = st.columns([1, 2])
    with col_a:
        button_clicked = st.button(
            "Calcular / actualizar pricing",
            type="primary" if not st.session_state.pricing_ready else "secondary",
            use_container_width=True,
        )
    with col_b:
        st.caption(
            "Pricing usa la base limpia + NSE y la elasticidad SKU × trimestre ya calculada. "
            "Cambiar filtros no recalcula elasticidad ni vuelve a simular todo."
        )

    if st.session_state.pricing_ready and not button_clicked:
        return True

    if not button_clicked and not st.session_state.pricing_ready:
        st.info("Presiona **Calcular / actualizar pricing** para ejecutar simulaciones y proyecciones.")
        return False

    try:
        pricing_key = (analysis_key, "pricing_depende_ventas_nse_y_elasticidad_sku_trimestre")
        cache_pr = st.session_state.manual_cache.setdefault("pricing", {})
        if pricing_key in cache_pr:
            base_pricing, simulacion, resumen_pricing = cache_pr[pricing_key]
        else:
            with st.spinner("Simulando escenarios de pricing con base NSE + elasticidad SKU-trimestre..."):
                base_pricing, simulacion, resumen_pricing = simulate_pricing_cached(
                    st.session_state.ventas_nse,
                    st.session_state.elasticidad,
                    st.session_state.bloques,
                )
            cache_pr.clear()
            cache_pr[pricing_key] = (base_pricing, simulacion, resumen_pricing)

        st.session_state.pricing_cache_key = pricing_key
        st.session_state.base_pricing = base_pricing
        st.session_state.simulacion = simulacion
        st.session_state.resumen_pricing = resumen_pricing
        st.session_state.pricing_ready = True
        st.session_state.ventas_base_pricing = st.session_state.ventas_nse
        st.success("Pricing calculado correctamente usando base NSE + elasticidad SKU-trimestre.")
        return True
    except Exception as exc:
        st.session_state.pricing_ready = False
        st.error(f"No se pudo calcular pricing dinámico: {exc}")
        return False

def require_processed() -> bool:
    """Valida que haya datos procesados."""
    if not st.session_state.processed:
        st.warning(
            "Carga una base de ventas y presiona **Procesar / actualizar datos** en el sidebar. "
            "Después, cada vista calcula únicamente lo que necesita."
        )
        return False
    return True


# =========================================================
# Vistas
# =========================================================

def render_quality_view() -> None:
    """Vista 1: carga y diagnóstico."""
    st.title("1. Carga y diagnóstico de datos")
    st.caption("Validación, limpieza, cruce NSE y semáforo de calidad.")

    st.markdown(
        """
        Esta vista solo ejecuta limpieza, cruce NSE y diagnóstico de calidad.  
        **No calcula elasticidad ni pricing**, para que la app cargue más rápido.
        """
    )

    if not require_processed():
        return

    ventas = st.session_state.ventas_nse
    semaforo = st.session_state.semaforo
    resumen_limpieza = st.session_state.resumen_limpieza
    calidad_varianza = st.session_state.calidad_varianza
    nse_info = st.session_state.nse_info

    if not semaforo.empty:
        row = semaforo.iloc[0]
        color = "#dc2626" if "Rojo" in row["Semaforo"] else "#f59e0b" if "Amarillo" in row["Semaforo"] else "#16a34a"
        st.markdown(
            f"""
            <div style="border:2px solid {color}; border-radius:16px; padding:18px; background:#ffffff;">
                <h3 style="margin-top:0;">Semáforo de calidad: {row['Semaforo']}</h3>
                <p style="margin-bottom:0;">{row['Interpretacion']}</p>
                <small>{row['Motivos']}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("KPIs de calidad")
    row = semaforo.iloc[0] if not semaforo.empty else {}
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi_card("Registros originales", f"{int(row.get('Filas_Originales', 0)):,}", "Antes de limpieza")
    with c2:
        render_kpi_card("Registros limpios", f"{int(row.get('Filas_Limpias', 0)):,}", "Después de limpieza")
    with c3:
        render_kpi_card("Registros eliminados", f"{int(row.get('Registros_Removidos', 0)):,}", f"{row.get('%_Registros_Removidos', 0):.1f}% removido")
    with c4:
        render_kpi_card("Datos faltantes", f"{row.get('Porcentaje_Datos_Faltantes_Original', 0):.1f}%", "Promedio original")

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        render_kpi_card("Duplicados", f"{int(row.get('Duplicados_Originales', 0)):,}", "Detectados originalmente")
    with c6:
        render_kpi_card("Valores infinitos", f"{int(row.get('Valores_Infinitos_Detectados', 0)):,}", "Antes de limpieza")
    with c7:
        render_kpi_card("Precio inválido", f"{int(row.get('Registros_Precio_Invalido', 0)):,}", "Después de crear precio")
    with c8:
        render_kpi_card("Cantidad inválida", f"{int(row.get('Registros_Cantidad_Invalida', 0)):,}", "qty <= 0")

    st.subheader("Cruce NSE")
    st.info(nse_info.get("mensaje", "NSE no aplicado."))
    if "categoria_est_socio" in ventas.columns:
        st.dataframe(
            ventas["categoria_est_socio"]
            .fillna("Sin dato")
            .value_counts(dropna=False)
            .rename_axis("categoria_est_socio")
            .reset_index(name="Registros"),
            use_container_width=True,
        )

    with st.expander("Resumen de limpieza"):
        st.dataframe(resumen_limpieza, use_container_width=True)

    with st.expander("Métricas de varianza"):
        st.dataframe(calidad_varianza, use_container_width=True)

    st.subheader("Vista previa de la base limpia y cruzada")
    st.dataframe(ventas.head(MAX_ROWS_PREVIEW), use_container_width=True)
    st.success("La base está lista. Pasa a Elasticidad o Pricing cuando quieras calcular esas vistas.")


def render_elasticity_view() -> None:
    """Vista 2: elasticidad."""
    st.title("2. Elasticidad")
    st.caption("Elasticidad log-log por SKU y bloques fijos de 3 meses.")

    if not require_processed():
        return

    if not ensure_elasticity_ready(show_button=True):
        return

    import plotly.express as px

    from modules.elasticity import build_dynamic_explanation_elasticity, build_elasticity_download
    from modules.utils import add_state_coordinates

    df = st.session_state.elasticidad
    ventas = st.session_state.ventas_base_elasticidad

    if df.empty:
        st.warning("No se generaron resultados de elasticidad. Revisa fechas, SKUs y variación de precios.")
        return

    with st.expander("Cómo interpretar este dashboard", expanded=True):
        st.markdown(
            """
            La elasticidad mide qué tanto cambia la demanda ante un cambio de precio.
            Una elasticidad entre **0 y -1** indica demanda inelástica: puede tolerar incrementos.
            Una elasticidad **menor a -1** indica demanda elástica: conviene tener cuidado con subidas y evaluar promociones.
            Una elasticidad **positiva** es sospechosa o requiere revisión, porque sugiere que precio y demanda suben juntos.
            Un **R² bajo** o **p-value alto** no invalida automáticamente el resultado, pero sí aumenta el riesgo de interpretación.
            """
        )

    st.subheader("Filtros")
    c1, c2, c3 = st.columns(3)

    dept_options = ["Todos"] + sorted(df["dept_nm"].dropna().astype(str).unique().tolist()) if "dept_nm" in df.columns else ["Todos"]
    with c1:
        dept = st.selectbox("Departamento", dept_options)

    df_dep = filter_dataframe_dependently(df, {"dept_nm": dept})

    tri_options = ["Todos"] + sorted(df_dep["trimestre"].dropna().astype(str).unique().tolist())
    with c2:
        trimestre = st.selectbox("Trimestre", tri_options)

    df_dep_tri = filter_dataframe_dependently(df_dep, {"trimestre": trimestre})

    sku_options = sorted(df_dep_tri["SKU"].dropna().astype(str).unique().tolist())
    with c3:
        skus = st.multiselect("SKU", sku_options, default=sku_options[: min(5, len(sku_options))])

    filtered = filter_dataframe_dependently(df_dep_tri, {"SKU": skus})

    if filtered.empty:
        st.warning("No hay datos para la selección actual.")
        return

    st.subheader("KPIs")
    elasticidad_prom = filtered["Elasticidad"].mean()
    beta_prom = filtered["Beta"].mean()
    r2_prom = filtered["R2"].mean()
    diagnostico_dom = (
        filtered["Diagnostico"].dropna().mode().iloc[0]
        if not filtered["Diagnostico"].dropna().mode().empty
        else "Sin diagnóstico"
    )

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        render_kpi_card("Elasticidad promedio", format_num(elasticidad_prom, 3), "Promedio filtrado")
    with k2:
        render_kpi_card("Beta promedio", format_num(beta_prom, 3), "Modelo log-log")
    with k3:
        render_kpi_card("R² promedio", format_num(r2_prom, 3), "Ajuste promedio")
    with k4:
        render_kpi_card("SKUs analizados", f"{filtered['SKU'].nunique():,}", "Únicos")
    with k5:
        render_kpi_card("Diagnóstico dominante", diagnostico_dom, "Moda")

    st.subheader("Curva de elasticidad")
    curva_df = filtered.dropna(subset=["Alfa", "Elasticidad"]).copy()
    if curva_df.empty or ventas.empty:
        st.warning("No hay alfa/elasticidad suficiente para construir la curva.")
    else:
        curva_plot = build_elasticity_curve_data(
            curva_df,
            float(ventas["precio_unitario"].quantile(0.05)),
            float(ventas["precio_unitario"].quantile(0.95)),
            MAX_SKUS_CURVA_ELASTICIDAD,
        )
        if not curva_plot.empty:
            fig = px.line(curva_plot, x="Demanda estimada", y="Precio", color="SKU", title="Curva de elasticidad estimada")
            st.plotly_chart(fig, use_container_width=True)
            st.caption(build_dynamic_explanation_elasticity(filtered, {"departamento": dept, "trimestre": trimestre, "SKU": ", ".join(skus[:5])}))

    st.subheader("Serie de tiempo de demanda")
    ventas_f = ventas
    if dept != "Todos" and "dept_nm" in ventas_f.columns:
        ventas_f = ventas_f[ventas_f["dept_nm"].astype(str) == str(dept)]
    if skus:
        ventas_f = ventas_f[ventas_f["prod_nbr"].astype(str).isin(skus)]

    if ventas_f.empty:
        st.warning("No hay ventas para la serie de tiempo con estos filtros.")
    else:
        serie = aggregate_weekly_demand(ventas_f)
        if "Promoción" in serie.columns:
            fig = px.line(serie, x="tran_date", y="Demanda", color="Promoción", title="Demanda semanal con/sin promoción")
        else:
            fig = px.line(serie, x="tran_date", y="Demanda", title="Demanda semanal")
        st.plotly_chart(fig, use_container_width=True)
        st.caption(build_dynamic_explanation_elasticity(filtered, {"departamento": dept, "trimestre": trimestre}))

    st.subheader("Mapa geográfico de México")
    estado_col = "estado" if "estado" in filtered.columns else None
    if estado_col is None or filtered[estado_col].dropna().empty:
        st.warning("No hay columna `estado` disponible para construir el mapa.")
    else:
        geo = (
            filtered.dropna(subset=[estado_col])
            .groupby(estado_col, as_index=False)
            .agg(Elasticidad=("Elasticidad", "mean"), SKUs=("SKU", "nunique"))
        )
        geo["Elasticidad absoluta"] = geo["Elasticidad"].abs()
        geo = add_state_coordinates(geo, estado_col=estado_col).dropna(subset=["lat", "lon"])
        if geo.empty:
            st.warning("No se pudieron homologar los estados a coordenadas de México.")
        else:
            fig = px.scatter_geo(
                geo,
                lat="lat",
                lon="lon",
                color="Elasticidad absoluta",
                size="Elasticidad absoluta",
                hover_name=estado_col,
                hover_data={"Elasticidad": ":.3f", "SKUs": True, "lat": False, "lon": False},
                scope="north america",
                title="Intensidad de elasticidad absoluta por estado",
            )
            fig.update_geos(fitbounds="locations", visible=True)
            st.plotly_chart(fig, use_container_width=True)
            st.caption(build_dynamic_explanation_elasticity(filtered, {"departamento": dept, "trimestre": trimestre, "estado": "mapa"}))

    st.subheader("Descarga")
    elasticidad_csv = build_elasticity_download(df)
    st.download_button(
        "Descargar CSV de elasticidad por SKU y trimestre",
        data=convert_df_to_csv(elasticidad_csv),
        file_name="elasticidad_por_sku_trimestre.csv",
        mime="text/csv",
    )


def render_pricing_view() -> None:
    """Vista 3: pricing dinámico y proyección.

    Iteraciones aplicadas:
    - Se quitaron los filtros de estado y nivel socioeconómico de la interfaz.
    - La dependencia de filtros queda en este orden:
      1) Categoría de SKU -> 2) Departamento -> 3) Trimestre -> 4) SKU.
    - Cada filtro delimita automáticamente las opciones de los siguientes.
    - La descarga completa se prepara bajo demanda y se entrega como ZIP con CSV,
      para evitar archivos corruptos o demasiado pesados en Streamlit/Excel.
    """
    st.title("3. Pricing dinámico + proyección de ventas")
    st.caption("Simulación de escenarios, KPIs, proyección y recomendación del mejor escenario.")
    st.info(
        "Esta vista depende de dos insumos: **base limpia + NSE** y **elasticidad SKU × trimestre**. "
        "Los filtros visibles son categoría, departamento, trimestre y SKU. "
        "El NSE sigue dentro de la base para el análisis, pero ya no aparece como filtro en esta vista."
    )

    if not require_processed():
        return

    if not ensure_pricing_ready():
        return

    import plotly.express as px

    from modules.pricing import build_dynamic_explanation_pricing, build_pricing_downloads

    sim = st.session_state.simulacion
    resumen = st.session_state.resumen_pricing

    if sim is None or sim.empty:
        st.warning("No hay simulaciones de pricing. Revisa elasticidad, costos y bloques trimestrales.")
        return

    # Validaciones mínimas para evitar errores por columnas faltantes.
    required_filter_cols = ["Categoria_RF", "trimestre", "SKU", "Nombre_Escenario"]
    missing = [c for c in required_filter_cols if c not in sim.columns]
    if missing:
        st.error(
            "La tabla de simulaciones no tiene las columnas necesarias para la vista de pricing: "
            + ", ".join(missing)
        )
        return

    st.subheader("Filtros")
    st.caption(
        "Orden de dependencia: **Categoría de SKU → Departamento → Trimestre → SKU**. "
        "Al cambiar un filtro, los siguientes muestran únicamente opciones válidas."
    )

    f1, f2, f3, f4 = st.columns(4)

    # 1) Categoría de SKU
    cat_options = ["Todas"] + _safe_sorted_options(sim, "Categoria_RF")
    categoria = _dependent_selectbox(
        label="1. Categoría de SKU",
        options=cat_options,
        key="pricing_filter_categoria",
        default="Todas",
        container=f1,
    )
    df_cat = _filter_fast(sim, "Categoria_RF", categoria)

    # 2) Departamento, delimitado por categoría.
    dept_col = "dept_nm" if "dept_nm" in df_cat.columns else None
    dept_options = ["Todos"] + (_safe_sorted_options(df_cat, dept_col) if dept_col else [])
    dept = _dependent_selectbox(
        label="2. Departamento",
        options=dept_options,
        key="pricing_filter_departamento",
        default="Todos",
        container=f2,
    )
    df_dept = _filter_fast(df_cat, dept_col, dept) if dept_col else df_cat

    # 3) Trimestre, delimitado por categoría + departamento.
    tri_options = ["Todos"] + _safe_sorted_options(df_dept, "trimestre")
    trimestre = _dependent_selectbox(
        label="3. Trimestre",
        options=tri_options,
        key="pricing_filter_trimestre",
        default="Todos",
        container=f3,
    )
    df_tri = _filter_fast(df_dept, "trimestre", trimestre)

    # 4) SKU, delimitado por categoría + departamento + trimestre.
    sku_options = ["Todos"] + _safe_sorted_options(df_tri, "SKU")
    sku = _dependent_selectbox(
        label="4. SKU",
        options=sku_options,
        key="pricing_filter_sku",
        default="Todos",
        container=f4,
    )
    df_sku = _filter_fast(df_tri, "SKU", sku)

    if df_sku.empty:
        st.warning("No hay resultados para la combinación de filtros seleccionada.")
        return

    # Escenario: se filtra después de la cascada principal.
    escenario_options = _safe_sorted_options(df_sku, "Nombre_Escenario")
    if not escenario_options:
        escenario_options = ESCENARIOS_PRICING["Nombre_Escenario"].astype(str).tolist()

    escenario = st.selectbox(
        "Escenario de pricing",
        escenario_options,
        key="pricing_filter_escenario",
    )

    selected = _filter_fast(df_sku, "Nombre_Escenario", escenario)

    if selected.empty:
        st.warning("No hay resultados para la combinación de filtros y escenario seleccionado.")
        return

    card1, card2 = st.columns(2)
    with card1:
        cat_sel = (
            selected["Categoria_RF"].dropna().mode().iloc[0]
            if "Categoria_RF" in selected.columns and not selected["Categoria_RF"].dropna().mode().empty
            else "Sin categoría"
        )
        render_kpi_card("Categoría del SKU/grupo", cat_sel, "Según reglas de elasticidad y rentabilidad")
    with card2:
        if sku != "Todos":
            best = resumen.copy() if resumen is not None else pd.DataFrame()
            if not best.empty and "SKU" in best.columns:
                best = best[best["SKU"].astype(str) == str(sku)]
                if trimestre != "Todos" and "trimestre" in best.columns:
                    best = best[best["trimestre"].astype(str) == str(trimestre)]
                best_scen = best["Escenario_Ideal"].iloc[0] if "Escenario_Ideal" in best.columns and not best.empty else "Sin dato"
            else:
                best_scen = "Sin dato"
            render_kpi_card("Mejor escenario", best_scen, "Para el SKU seleccionado")
        else:
            render_kpi_card("Mejor escenario", "Selecciona un SKU", "Disponible por SKU")

    st.subheader("KPIs proyectados")
    unidades = selected["Unidades_Simuladas"].sum() if "Unidades_Simuladas" in selected.columns else 0
    ingreso = selected["Ingreso_Simulado"].sum() if "Ingreso_Simulado" in selected.columns else 0
    margen = selected["Margen_Simulado"].sum() if "Margen_Simulado" in selected.columns else 0

    k1, k2, k3 = st.columns(3)
    with k1:
        render_kpi_card("Unidades simuladas", format_num(unidades, 0), escenario)
    with k2:
        render_kpi_card("Ingreso predicho", format_money(ingreso), escenario)
    with k3:
        render_kpi_card("Margen predicho", format_money(margen), escenario)

    money_long, qty_long, im_long = aggregate_pricing_chart_data(selected)

    st.subheader("Ventas en dinero")
    if not money_long.empty:
        fig = px.line(
            money_long,
            x="trimestre",
            y="Ventas",
            color="Serie",
            markers=True,
            title="Ventas normales vs ventas simuladas",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No hay datos suficientes para graficar ventas en dinero.")
    st.caption(build_dynamic_explanation_pricing(selected, escenario, None if sku == "Todos" else sku))

    st.subheader("Ventas en cantidad")
    if not qty_long.empty:
        fig = px.line(
            qty_long,
            x="trimestre",
            y="Unidades",
            color="Serie",
            markers=True,
            title="Cantidad normal vs cantidad simulada",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No hay datos suficientes para graficar ventas en cantidad.")
    st.caption(build_dynamic_explanation_pricing(selected, escenario, None if sku == "Todos" else sku))

    st.subheader("Ingreso vs margen")
    if not im_long.empty:
        fig = px.bar(
            im_long,
            x="trimestre",
            y="Monto",
            color="Métrica",
            barmode="group",
            title="Ingreso simulado vs margen simulado",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No hay datos suficientes para graficar ingreso vs margen.")
    st.caption(build_dynamic_explanation_pricing(selected, escenario, None if sku == "Todos" else sku))

    st.subheader("Conclusión personalizada")
    st.info(build_dynamic_explanation_pricing(selected, escenario, None if sku == "Todos" else sku))

    with st.expander("Tabla de resultados filtrados"):
        cols = [
            "SKU",
            "trimestre",
            "Nombre_Escenario",
            "Categoria_RF",
            "dept_nm",
            "Elasticidad",
            "R2",
            "P_Value",
            "Unidades_Base",
            "Unidades_Simuladas",
            "Ingreso_Base",
            "Ingreso_Simulado",
            "Margen_Base",
            "Margen_Simulado",
            "Escenario_Ideal",
        ]
        st.dataframe(selected[[c for c in cols if c in selected.columns]], use_container_width=True)

    st.subheader("Descargas")
    st.caption(
        "Para evitar archivos corruptos o muy pesados, los archivos se preparan solo cuando presionas el botón. "
        "El archivo completo de todos los escenarios se descarga como ZIP con un CSV adentro."
    )

    download_key = st.session_state.get("pricing_cache_key")
    prepared_key = st.session_state.get("pricing_download_key")
    downloads_ready = prepared_key == download_key and st.session_state.get("pricing_full_zip_bytes") is not None

    if st.button("Preparar archivos de descarga", use_container_width=True):
        try:
            with st.spinner("Preparando archivos de descarga..."):
                exp_csv, best_csv = build_pricing_downloads(sim, resumen)

                if exp_csv is None or exp_csv.empty:
                    st.warning("No se pudo construir el archivo completo porque la tabla de simulaciones está vacía.")
                    st.session_state.pricing_download_key = None
                    st.session_state.pricing_full_zip_bytes = None
                    st.session_state.pricing_best_csv_bytes = None
                else:
                    st.session_state.pricing_full_zip_bytes = _dataframes_to_zip_csv_bytes(
                        {
                            "pricing_todos_los_escenarios.csv": exp_csv,
                        },
                        sep=";",
                    )
                    st.session_state.pricing_best_csv_bytes = _df_to_excel_friendly_csv_bytes(best_csv, sep=";")
                    st.session_state.pricing_download_rows = len(exp_csv)
                    st.session_state.pricing_best_rows = len(best_csv) if best_csv is not None else 0
                    st.session_state.pricing_download_key = download_key
                    st.success("Archivos preparados correctamente.")
        except Exception as exc:
            st.error(f"No se pudieron preparar las descargas: {exc}")
            st.session_state.pricing_download_key = None
            st.session_state.pricing_full_zip_bytes = None
            st.session_state.pricing_best_csv_bytes = None

    prepared_key = st.session_state.get("pricing_download_key")
    downloads_ready = prepared_key == download_key and st.session_state.get("pricing_full_zip_bytes") is not None

    if downloads_ready:
        rows_full = st.session_state.get("pricing_download_rows", 0)
        if rows_full > 1_048_576:
            st.warning(
                f"El archivo completo tiene {rows_full:,} filas. Excel tiene un límite aproximado de 1,048,576 filas por hoja. "
                "El CSV está completo dentro del ZIP, pero para bases muy grandes conviene abrirlo en Power BI, Python, Tableau o dividirlo por filtros."
            )

        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                "Descargar ZIP con CSV completo de todos los escenarios",
                data=st.session_state.pricing_full_zip_bytes,
                file_name="pricing_todos_los_escenarios.zip",
                mime="application/zip",
                use_container_width=True,
            )
        with d2:
            best_bytes = st.session_state.get("pricing_best_csv_bytes") or b""
            st.download_button(
                "Descargar CSV con mejor escenario",
                data=best_bytes,
                file_name="pricing_mejor_escenario.csv",
                mime="text/csv; charset=utf-8",
                use_container_width=True,
                disabled=not bool(best_bytes),
            )
    else:
        st.info("Presiona **Preparar archivos de descarga** para generar los archivos.")


# =========================================================
# Router principal: solo una vista por rerun
# =========================================================

def main() -> None:
    """Punto de entrada de la app."""
    init_state()
    vista = render_sidebar()

    # Router explícito: solo se ejecuta una rama por rerun.
    if vista.startswith("1."):
        render_quality_view()
        return

    if vista.startswith("2."):
        render_elasticity_view()
        return

    render_pricing_view()


if __name__ == "__main__":
    main()
