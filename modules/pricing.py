"""Simulación de pricing dinámico y selección de mejores escenarios."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (
    ELASTICIDAD_CAP_MAX,
    ELASTICIDAD_CAP_MIN,
    ESCENARIOS_PRICING,
    LIMITE_NUMERICO_RF,
    MIN_OBSERVACIONES,
    MIN_PRECIOS_DISTINTOS,
    USE_RANDOM_FOREST_CLASSIFIER,
)
from .utils import format_money, format_num, format_pct, normalizar_categoria_est_socio


def _moda_no_vacia(serie: pd.Series):
    s = serie.copy()
    s = s.replace(["", " ", "nan", "NaN", "None", "none", "null", "Null"], np.nan)
    s = s.dropna()
    if s.empty:
        return "Sin dato"
    moda = s.mode(dropna=True)
    if not moda.empty:
        return moda.iloc[0]
    return s.iloc[0]


def categorize_sku(row: pd.Series) -> str:
    """
    Clasificación por reglas del notebook base.
    Nota: el notebook asignaba elasticidad positiva a Mantener precio; esta app conserva
    esa categoría internamente, aunque el usuario puede filtrar No recomendar si desea.
    """
    elasticidad = row.get("Elasticidad", np.nan)
    n_obs = row.get("Observaciones", np.nan)
    n_precios = row.get("Precios_Distintos", np.nan)

    datos_insuficientes = (
        pd.isna(elasticidad)
        or (pd.notna(n_obs) and n_obs < MIN_OBSERVACIONES)
        or (pd.notna(n_precios) and n_precios < MIN_PRECIOS_DISTINTOS)
    )

    if datos_insuficientes:
        return "No recomendar"
    if elasticidad >= 0:
        return "Mantener precio"
    if -1 <= elasticidad < 0:
        return "Subir precio"
    if elasticidad < -1:
        return "Bajar precio / promociones"
    return "No recomendar"


def _prepare_financial_base(ventas_base: pd.DataFrame, elasticidad_df: pd.DataFrame, bloques: list[dict]) -> pd.DataFrame:
    """Crea base financiera SKU-trimestre."""
    mapa_mes_periodo = {}
    for bloque in bloques:
        for mes in bloque["meses"]:
            mapa_mes_periodo[mes] = {
                "periodo_3m": bloque["periodo_3m"],
                "trimestre": bloque["trimestre"],
                "mes_inicio": str(bloque["mes_inicio"]),
                "mes_fin": str(bloque["mes_fin"]),
            }

    ventas = ventas_base.copy()

    if "mes" not in ventas.columns:
        ventas["mes"] = pd.to_datetime(ventas["tran_date"], errors="coerce").dt.to_period("M")

    ventas["periodo_3m"] = ventas["mes"].map(lambda x: mapa_mes_periodo.get(x, {}).get("periodo_3m", np.nan))
    ventas["trimestre"] = ventas["mes"].map(lambda x: mapa_mes_periodo.get(x, {}).get("trimestre", np.nan))
    ventas["mes_inicio"] = ventas["mes"].map(lambda x: mapa_mes_periodo.get(x, {}).get("mes_inicio", np.nan))
    ventas["mes_fin"] = ventas["mes"].map(lambda x: mapa_mes_periodo.get(x, {}).get("mes_fin", np.nan))
    ventas = ventas.dropna(subset=["periodo_3m"]).copy()

    if "costo_unitario" not in ventas.columns:
        if "costo2" not in ventas.columns:
            raise ValueError("No existe costo_unitario ni costo2 para calcular margen.")
        ventas["costo_unitario"] = pd.to_numeric(ventas["costo2"], errors="coerce")

    ventas["costo_unitario"] = pd.to_numeric(ventas["costo_unitario"], errors="coerce")
    ventas["precio_unitario"] = pd.to_numeric(ventas["precio_unitario"], errors="coerce")
    ventas["costo_total_linea"] = ventas["costo_unitario"] * ventas["qty"]
    ventas["margen_unitario"] = ventas["precio_unitario"] - ventas["costo_unitario"]
    ventas["margen_total"] = ventas["margen_unitario"] * ventas["qty"]

    if "categoria_est_socio" in ventas.columns:
        ventas["categoria_est_socio"] = ventas["categoria_est_socio"].apply(normalizar_categoria_est_socio)

    aggs = {
        "Venta_Neta_Total": ("net_sale", "sum"),
        "Unidades_Base": ("qty", "sum"),
        "Costo_Total": ("costo_total_linea", "sum"),
        "Margen_Base": ("margen_total", "sum"),
        "Ticket_Promedio_Linea": ("net_sale", "mean"),
        "Precio_Promedio_Linea": ("precio_unitario", "mean"),
    }

    descriptoras = ["dept_nm", "subdept_nm", "marca", "tipo_marca", "categoria_est_socio", "estado"]
    for col in descriptoras:
        if col in ventas.columns:
            aggs[col] = (col, _moda_no_vacia)

    base_financiera = (
        ventas.groupby(["prod_nbr", "periodo_3m", "trimestre", "mes_inicio", "mes_fin"], as_index=False)
        .agg(**aggs)
    )

    base_financiera["Precio_Base"] = base_financiera["Venta_Neta_Total"] / base_financiera["Unidades_Base"]
    base_financiera["Costo_Unitario_Base"] = base_financiera["Costo_Total"] / base_financiera["Unidades_Base"]
    base_financiera["Margen_Unitario_Base"] = base_financiera["Precio_Base"] - base_financiera["Costo_Unitario_Base"]
    base_financiera["Ingreso_Base"] = base_financiera["Precio_Base"] * base_financiera["Unidades_Base"]

    cols_fin = [
        "Venta_Neta_Total",
        "Unidades_Base",
        "Costo_Total",
        "Margen_Base",
        "Ticket_Promedio_Linea",
        "Precio_Promedio_Linea",
        "Precio_Base",
        "Costo_Unitario_Base",
        "Margen_Unitario_Base",
        "Ingreso_Base",
    ]

    for col in cols_fin:
        if col in base_financiera.columns:
            base_financiera[col] = pd.to_numeric(base_financiera[col], errors="coerce")

    base_financiera = base_financiera.replace([np.inf, -np.inf], np.nan)
    base_financiera = base_financiera[
        (base_financiera["Unidades_Base"] > 0) & (base_financiera["Precio_Base"] > 0)
    ].copy()

    elasticidad = elasticidad_df.copy()
    elasticidad["prod_nbr"] = elasticidad["prod_nbr"].astype(str)
    base_financiera["prod_nbr"] = base_financiera["prod_nbr"].astype(str)

    base_pricing = base_financiera.merge(
        elasticidad,
        on=["prod_nbr", "periodo_3m", "trimestre", "mes_inicio", "mes_fin"],
        how="left",
        suffixes=("", "_elasticidad"),
    )
    base_pricing["SKU"] = base_pricing["prod_nbr"]

    for col in descriptoras:
        col_el = f"{col}_elasticidad"
        if col in base_pricing.columns and col_el in base_pricing.columns:
            base_pricing[col] = base_pricing[col].replace(["Sin dato", ""], np.nan).fillna(base_pricing[col_el])
        elif col_el in base_pricing.columns:
            base_pricing[col] = base_pricing[col_el]

    return base_pricing


def _classify_with_conservative_rf(base_pricing: pd.DataFrame) -> pd.DataFrame:
    """Clasifica SKUs. Por rendimiento, usa reglas salvo que se active RF en config.py."""
    df_rf = base_pricing.copy()

    # Clasificación vectorizada para evitar apply fila por fila en bases grandes.
    elasticidad = pd.to_numeric(df_rf.get("Elasticidad", np.nan), errors="coerce")
    n_obs = pd.to_numeric(df_rf.get("Observaciones", np.nan), errors="coerce")
    n_precios = pd.to_numeric(df_rf.get("Precios_Distintos", np.nan), errors="coerce")
    datos_insuficientes = (
        elasticidad.isna()
        | (n_obs.notna() & (n_obs < MIN_OBSERVACIONES))
        | (n_precios.notna() & (n_precios < MIN_PRECIOS_DISTINTOS))
    )
    df_rf["Categoria_Regla"] = np.select(
        [
            datos_insuficientes,
            elasticidad >= 0,
            (elasticidad >= -1) & (elasticidad < 0),
            elasticidad < -1,
        ],
        [
            "No recomendar",
            "Mantener precio",
            "Subir precio",
            "Bajar precio / promociones",
        ],
        default="No recomendar",
    )

    # Evita entrenar scikit-learn en cada procesamiento. Esto hace mucho más rápida la app
    # y mantiene la lógica principal de categorización por reglas.
    if not USE_RANDOM_FOREST_CLASSIFIER:
        df_rf["Categoria_RF"] = df_rf["Categoria_Regla"]
        df_rf["Categoria_RF_Original"] = df_rf["Categoria_Regla"]
        df_rf["Probabilidad_RF_Max"] = 1.0
        return df_rf

    # Imports diferidos: scikit-learn solo se carga si activas USE_RANDOM_FOREST_CLASSIFIER=True.
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder

    features_numericas = [
        "Elasticidad",
        "R2",
        "P_Value",
        "Tiene_Promocion",
        "Num_Promociones",
        "Precio_Base",
        "Costo_Unitario_Base",
        "Margen_Unitario_Base",
        "Unidades_Base",
        "Ingreso_Base",
        "Margen_Base",
        "Ticket_Promedio_Linea",
        "Precio_Promedio_Linea",
    ]

    features_categoricas_base = ["dept_nm", "subdept_nm", "marca", "tipo_marca", "categoria_est_socio"]
    features_categoricas = [col for col in features_categoricas_base if col in df_rf.columns]
    features_numericas = [col for col in features_numericas if col in df_rf.columns]

    for col in features_categoricas:
        df_rf[col] = (
            df_rf[col].astype("string")
            .str.strip()
            .replace(["", "nan", "NaN", "None", "none", "null", "Null"], pd.NA)
            .fillna("Sin dato")
        )

    for col in features_numericas:
        df_rf[col] = pd.to_numeric(df_rf[col], errors="coerce")
        df_rf[col] = df_rf[col].replace([np.inf, -np.inf], np.nan)
        df_rf[col] = df_rf[col].clip(lower=-LIMITE_NUMERICO_RF, upper=LIMITE_NUMERICO_RF)

    if "Elasticidad" in df_rf.columns:
        df_rf["Elasticidad_Disponible"] = df_rf["Elasticidad"].notna().astype(int)
        features_numericas.append("Elasticidad_Disponible")
    if "R2" in df_rf.columns:
        df_rf["R2_Disponible"] = df_rf["R2"].notna().astype(int)
        features_numericas.append("R2_Disponible")
    if "P_Value" in df_rf.columns:
        df_rf["PValue_Disponible"] = df_rf["P_Value"].notna().astype(int)
        features_numericas.append("PValue_Disponible")

    features_numericas = [
        col for col in dict.fromkeys(features_numericas)
        if col in df_rf.columns and df_rf[col].notna().any()
    ]
    features_modelo = features_numericas + features_categoricas

    if df_rf.empty or not features_modelo or df_rf["Categoria_Regla"].nunique() <= 1 or len(df_rf) < 20:
        df_rf["Categoria_RF"] = df_rf["Categoria_Regla"]
        df_rf["Categoria_RF_Original"] = df_rf["Categoria_Regla"]
        df_rf["Probabilidad_RF_Max"] = 1.0
        return df_rf

    X = df_rf[features_modelo].copy()
    y = df_rf["Categoria_Regla"].copy()

    transformers = []
    if features_numericas:
        transformers.append(("num", SimpleImputer(strategy="median"), features_numericas))
    if features_categoricas:
        transformers.append(
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                features_categoricas,
            )
        )

    preprocessor = ColumnTransformer(transformers=transformers, remainder="drop")

    min_leaf = max(5, int(np.ceil(len(df_rf) * 0.015)))
    min_split = max(12, int(np.ceil(len(df_rf) * 0.03)))

    model = RandomForestClassifier(
        n_estimators=120,
        max_depth=3,
        max_leaf_nodes=6,
        min_samples_leaf=min_leaf,
        min_samples_split=min_split,
        max_features="sqrt",
        bootstrap=True,
        max_samples=0.70,
        random_state=42,
        class_weight="balanced_subsample",
        n_jobs=-1,
    )

    pipeline = Pipeline(steps=[("preprocesador", preprocessor), ("modelo", model)])

    try:
        pipeline.fit(X, y)
        df_rf["Categoria_RF"] = pipeline.predict(X)
        proba = pipeline.predict_proba(X)
        df_rf["Probabilidad_RF_Max"] = proba.max(axis=1)
        df_rf["Categoria_RF_Original"] = df_rf["Categoria_RF"]
        df_rf.loc[df_rf["Probabilidad_RF_Max"] < 0.45, "Categoria_RF"] = "No recomendar"
    except Exception:
        df_rf["Categoria_RF"] = df_rf["Categoria_Regla"]
        df_rf["Categoria_RF_Original"] = df_rf["Categoria_Regla"]
        df_rf["Probabilidad_RF_Max"] = 1.0

    return df_rf


def simulate_pricing_scenarios(
    ventas_base: pd.DataFrame,
    elasticidad_df: pd.DataFrame,
    bloques: list[dict],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Simula todos los escenarios por SKU-trimestre y elige mejor escenario.

    Versión optimizada: usa un cross join vectorizado en lugar de loops fila por
    fila. Mantiene la misma lógica de escenarios, elasticidad capada, ingreso,
    margen, categoría y selección del mejor escenario.
    """
    base_pricing = _prepare_financial_base(ventas_base, elasticidad_df, bloques)
    base_pricing = _classify_with_conservative_rf(base_pricing)

    if base_pricing.empty:
        return base_pricing, pd.DataFrame(), pd.DataFrame()

    base = base_pricing.copy()
    esc = ESCENARIOS_PRICING.copy()

    base["_join_key"] = 1
    esc["_join_key"] = 1
    simulacion = base.merge(esc, on="_join_key", how="left").drop(columns="_join_key")

    cambio = pd.to_numeric(simulacion["Cambio_Efectivo"], errors="coerce")
    elasticidad_original = pd.to_numeric(simulacion["Elasticidad"], errors="coerce")
    precio_base = pd.to_numeric(simulacion["Precio_Base"], errors="coerce")
    costo_unitario = pd.to_numeric(simulacion["Costo_Unitario_Base"], errors="coerce")
    unidades_base = pd.to_numeric(simulacion["Unidades_Base"], errors="coerce")
    ingreso_base = pd.to_numeric(simulacion["Ingreso_Base"], errors="coerce")
    margen_base = pd.to_numeric(simulacion["Margen_Base"], errors="coerce")

    valid = (
        elasticidad_original.notna()
        & precio_base.notna()
        & costo_unitario.notna()
        & unidades_base.notna()
        & (precio_base > 0)
        & (unidades_base > 0)
        & (1 + cambio > 0)
    )

    simulacion["Precio_Nuevo"] = np.where(valid, precio_base * (1 + cambio), np.nan)
    elasticidad_usada = elasticidad_original.clip(ELASTICIDAD_CAP_MIN, ELASTICIDAD_CAP_MAX)
    simulacion["Elasticidad_Usada"] = np.where(valid, elasticidad_usada, np.nan)
    simulacion["Elasticidad_Capada"] = np.where(valid, elasticidad_usada != elasticidad_original, True)

    unidades_sim = np.where(
        valid,
        unidades_base * np.exp(elasticidad_usada * np.log1p(cambio)),
        np.nan,
    )
    simulacion["Unidades_Simuladas"] = unidades_sim
    simulacion["Ingreso_Simulado"] = simulacion["Precio_Nuevo"] * simulacion["Unidades_Simuladas"]
    simulacion["Margen_Simulado"] = (simulacion["Precio_Nuevo"] - costo_unitario) * simulacion["Unidades_Simuladas"]

    for col in ["Unidades_Simuladas", "Ingreso_Simulado", "Margen_Simulado"]:
        simulacion[col] = pd.to_numeric(simulacion[col], errors="coerce").replace([np.inf, -np.inf], np.nan)

    simulacion["Cambio_Unidades"] = simulacion["Unidades_Simuladas"] - unidades_base
    simulacion["Cambio_Ingreso"] = simulacion["Ingreso_Simulado"] - ingreso_base
    simulacion["Cambio_Margen"] = simulacion["Margen_Simulado"] - margen_base

    simulacion["Cambio_Unidades_%"] = np.where(
        unidades_base != 0,
        ((simulacion["Unidades_Simuladas"] / unidades_base) - 1) * 100,
        np.nan,
    )
    simulacion["Cambio_Ingreso_%"] = np.where(
        ingreso_base != 0,
        ((simulacion["Ingreso_Simulado"] / ingreso_base) - 1) * 100,
        np.nan,
    )
    simulacion["Cambio_Margen_%"] = np.where(
        margen_base != 0,
        ((simulacion["Margen_Simulado"] / margen_base) - 1) * 100,
        np.nan,
    )

    rename_map = {
        "Cambio_Efectivo": "Cambio_Precio",
        "Nombre_Escenario": "Nombre_Escenario",
        "Nombre_Corto": "Nombre_Corto",
        "Tipo_Escenario": "Tipo_Escenario",
        "Mecanica_Promocion": "Mecanica_Promocion",
        "Observaciones_Modelo": "Observaciones",
        "Precios_Distintos_Modelo": "Precios_Distintos",
    }
    simulacion = simulacion.rename(columns=rename_map)

    simulacion["Cambio_Precio_%"] = simulacion["Cambio_Precio"] * 100
    simulacion["Descuento_Equivalente_%"] = np.where(
        simulacion["Cambio_Precio"] < 0,
        simulacion["Cambio_Precio"].abs() * 100,
        0,
    )

    if "Tiene_Promocion" not in simulacion.columns:
        simulacion["Tiene_Promocion"] = simulacion.get("tiene_promocion", np.nan)
    if "Num_Promociones" not in simulacion.columns:
        simulacion["Num_Promociones"] = simulacion.get("num_promociones", np.nan)

    # Homologa nombres esperados por vistas y descargas.
    column_defaults = {
        "Beta": np.nan,
        "R2": np.nan,
        "P_Value": np.nan,
        "Observaciones": np.nan,
        "Precios_Distintos": np.nan,
        "Tiene_Promocion": np.nan,
        "Num_Promociones": np.nan,
        "Probabilidad_RF_Max": np.nan,
        "Categoria_Regla": np.nan,
        "Categoria_RF": np.nan,
        "dept_nm": np.nan,
        "subdept_nm": np.nan,
        "marca": np.nan,
        "tipo_marca": np.nan,
        "categoria_est_socio": np.nan,
        "estado": np.nan,
    }
    for col, default in column_defaults.items():
        if col not in simulacion.columns:
            simulacion[col] = default

    # Ordena columnas clave primero para mantener salida amigable.
    front_cols = [
        "SKU", "prod_nbr", "periodo_3m", "trimestre", "mes_inicio", "mes_fin",
        "Categoria_Regla", "Categoria_RF", "Probabilidad_RF_Max", "Elasticidad",
        "Beta", "R2", "P_Value", "Observaciones", "Precios_Distintos",
        "Tiene_Promocion", "Num_Promociones", "Escenario_ID", "Nombre_Escenario",
        "Nombre_Corto", "Tipo_Escenario", "Mecanica_Promocion", "Cambio_Precio",
        "Cambio_Precio_%", "Descuento_Equivalente_%", "Precio_Base", "Precio_Nuevo",
        "Costo_Unitario_Base", "Unidades_Base", "Unidades_Simuladas",
        "Cambio_Unidades", "Cambio_Unidades_%", "Ingreso_Base", "Ingreso_Simulado",
        "Cambio_Ingreso", "Cambio_Ingreso_%", "Margen_Base", "Margen_Simulado",
        "Cambio_Margen", "Cambio_Margen_%", "Elasticidad_Usada", "Elasticidad_Capada",
        "dept_nm", "subdept_nm", "marca", "tipo_marca", "categoria_est_socio", "estado",
    ]
    rest_cols = [c for c in simulacion.columns if c not in front_cols]
    simulacion = simulacion[[c for c in front_cols if c in simulacion.columns] + rest_cols]

    resumen = (
        simulacion.groupby(["SKU", "periodo_3m"], as_index=False, group_keys=False)
        .apply(choose_best_scenario)
        .reset_index(drop=True)
    )

    cols_ideal = [
        "SKU",
        "periodo_3m",
        "Escenario_Ideal",
        "Escenario_ID_Ideal",
        "Tipo_Escenario_Ideal",
        "Mecanica_Promocion_Ideal",
        "Cambio_Precio_Ideal_%",
        "Criterio_Escenario_Ideal",
    ]

    simulacion = simulacion.merge(resumen[cols_ideal], on=["SKU", "periodo_3m"], how="left")

    return base_pricing, simulacion, resumen

def _fila_base_o_neutra(g: pd.DataFrame) -> pd.Series:
    base = g[g["Cambio_Precio"].abs() < 1e-9]
    if not base.empty:
        return base.iloc[0]
    return g.iloc[(g["Cambio_Precio"].abs()).argsort()].iloc[0]


def choose_best_scenario(g: pd.DataFrame) -> pd.Series:
    """Selecciona el escenario ideal por SKU-trimestre según categoría."""
    g = g.copy()
    categoria = g["Categoria_RF"].iloc[0]
    fila_base = _fila_base_o_neutra(g)

    g_valid = g.dropna(subset=["Unidades_Simuladas", "Ingreso_Simulado", "Margen_Simulado"]).copy()

    if g_valid.empty or categoria == "No recomendar":
        fila = fila_base
        criterio = "Sin recomendación por datos insuficientes o baja confianza"
    elif categoria == "Mantener precio":
        fila = fila_base
        criterio = "Mantener precio por elasticidad positiva o sin señal clara"
    elif categoria == "Subir precio":
        candidatos = g_valid[(g_valid["Cambio_Precio"] >= 0) & (g_valid["Cambio_Margen"] >= 0)].copy()
        if candidatos.empty:
            candidatos = g_valid.copy()
        fila = candidatos.sort_values(["Margen_Simulado", "Ingreso_Simulado", "Unidades_Simuladas"], ascending=[False, False, False]).iloc[0]
        criterio = "Maximiza margen simulado con escenario de subida o neutro"
    elif categoria == "Bajar precio / promociones":
        candidatos = g_valid[(g_valid["Cambio_Precio"] < 0) | (g_valid["Tipo_Escenario"] == "Promoción")].copy()
        if candidatos.empty:
            candidatos = g_valid.copy()
        fila = candidatos.sort_values(["Unidades_Simuladas", "Ingreso_Simulado", "Margen_Simulado"], ascending=[False, False, False]).iloc[0]
        criterio = "Maximiza unidades simuladas con descuento/promoción"
    else:
        fila = g_valid.sort_values(["Margen_Simulado", "Ingreso_Simulado", "Unidades_Simuladas"], ascending=[False, False, False]).iloc[0]
        criterio = "Maximiza margen, ingreso y unidades simuladas"

    max_unidades = g_valid.loc[g_valid["Unidades_Simuladas"].idxmax()] if not g_valid.empty else fila_base
    max_ingreso = g_valid.loc[g_valid["Ingreso_Simulado"].idxmax()] if not g_valid.empty else fila_base
    max_margen = g_valid.loc[g_valid["Margen_Simulado"].idxmax()] if not g_valid.empty else fila_base

    return pd.Series(
        {
            "SKU": fila["SKU"],
            "prod_nbr": fila["prod_nbr"],
            "periodo_3m": fila["periodo_3m"],
            "trimestre": fila["trimestre"],
            "mes_inicio": fila["mes_inicio"],
            "mes_fin": fila["mes_fin"],
            "Categoria_Regla": fila["Categoria_Regla"],
            "Categoria_RF": fila["Categoria_RF"],
            "Probabilidad_RF_Max": fila["Probabilidad_RF_Max"],
            "Elasticidad": fila["Elasticidad"],
            "Beta": fila["Beta"],
            "R2": fila["R2"],
            "P_Value": fila["P_Value"],
            "Observaciones": fila["Observaciones"],
            "Precios_Distintos": fila["Precios_Distintos"],
            "Tiene_Promocion": fila["Tiene_Promocion"],
            "Num_Promociones": fila["Num_Promociones"],
            "Precio_Base": fila["Precio_Base"],
            "Costo_Unitario_Base": fila["Costo_Unitario_Base"],
            "Unidades_Base": fila["Unidades_Base"],
            "Ingreso_Base": fila["Ingreso_Base"],
            "Margen_Base": fila["Margen_Base"],
            "Escenario_Ideal": fila["Nombre_Escenario"],
            "Escenario_ID_Ideal": fila["Escenario_ID"],
            "Tipo_Escenario_Ideal": fila["Tipo_Escenario"],
            "Mecanica_Promocion_Ideal": fila["Mecanica_Promocion"],
            "Cambio_Precio_Ideal_%": fila["Cambio_Precio_%"],
            "Precio_Nuevo_Ideal": fila["Precio_Nuevo"],
            "Unidades_Simuladas_Ideal": fila["Unidades_Simuladas"],
            "Ingreso_Simulado_Ideal": fila["Ingreso_Simulado"],
            "Margen_Simulado_Ideal": fila["Margen_Simulado"],
            "Cambio_Unidades_Ideal_%": fila["Cambio_Unidades_%"],
            "Cambio_Ingreso_Ideal_%": fila["Cambio_Ingreso_%"],
            "Cambio_Margen_Ideal_%": fila["Cambio_Margen_%"],
            "Criterio_Escenario_Ideal": criterio,
            "Escenario_Max_Unidades": max_unidades["Nombre_Escenario"],
            "Unidades_Max": max_unidades["Unidades_Simuladas"],
            "Escenario_Max_Ingreso": max_ingreso["Nombre_Escenario"],
            "Ingreso_Max": max_ingreso["Ingreso_Simulado"],
            "Escenario_Max_Margen": max_margen["Nombre_Escenario"],
            "Margen_Max": max_margen["Margen_Simulado"],
            "dept_nm": fila.get("dept_nm", np.nan),
            "subdept_nm": fila.get("subdept_nm", np.nan),
            "marca": fila.get("marca", np.nan),
            "tipo_marca": fila.get("tipo_marca", np.nan),
            "categoria_est_socio": fila.get("categoria_est_socio", np.nan),
            "estado": fila.get("estado", np.nan),
        }
    )


def build_pricing_downloads(simulacion: pd.DataFrame, resumen: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Construye los CSV obligatorios de pricing."""
    if simulacion is None or simulacion.empty:
        return pd.DataFrame(), pd.DataFrame()

    exp = simulacion.copy()
    exp_out = pd.DataFrame(
        {
            "SKU": exp.get("SKU"),
            "dept_nm": exp.get("dept_nm"),
            "marca": exp.get("marca"),
            "tipo_marca": exp.get("tipo_marca"),
            "categoria_est_socio": exp.get("categoria_est_socio"),
            "trimestre": exp.get("trimestre"),
            "escenario aplicado": exp.get("Nombre_Escenario"),
            "unidades simuladas": exp.get("Unidades_Simuladas"),
            "ingreso simulado": exp.get("Ingreso_Simulado"),
            "margen simulado": exp.get("Margen_Simulado"),
            "mejor escenario": exp.get("Escenario_Ideal"),
            "categoría de SKU": exp.get("Categoria_RF"),
        }
    )

    if resumen is None or resumen.empty:
        return exp_out, pd.DataFrame()

    best = resumen.copy()
    best_out = pd.DataFrame(
        {
            "SKU": best.get("SKU"),
            "trimestre": best.get("trimestre"),
            "categoría de SKU": best.get("Categoria_RF"),
            "dept_nm": best.get("dept_nm"),
            "marca": best.get("marca"),
            "tipo_marca": best.get("tipo_marca"),
            "categoria_est_socio": best.get("categoria_est_socio"),
            "elasticidad": best.get("Elasticidad"),
            "unidades simuladas": best.get("Unidades_Simuladas_Ideal"),
            "ingreso simulado": best.get("Ingreso_Simulado_Ideal"),
            "margen simulado": best.get("Margen_Simulado_Ideal"),
            "mejor escenario": best.get("Escenario_Ideal"),
        }
    )

    return exp_out, best_out


def build_dynamic_explanation_pricing(
    df_selected: pd.DataFrame,
    escenario: str,
    sku: str | None = None,
) -> str:
    """Explicación dinámica para pricing."""
    if df_selected is None or df_selected.empty:
        return "No hay datos suficientes para explicar esta selección."

    unidades_base = df_selected["Unidades_Base"].sum()
    unidades_sim = df_selected["Unidades_Simuladas"].sum()
    ingreso_base = df_selected["Ingreso_Base"].sum()
    ingreso_sim = df_selected["Ingreso_Simulado"].sum()
    margen_base = df_selected["Margen_Base"].sum()
    margen_sim = df_selected["Margen_Simulado"].sum()
    elasticidad_prom = df_selected["Elasticidad"].mean()
    categoria = (
        df_selected["Categoria_RF"].dropna().mode().iloc[0]
        if not df_selected["Categoria_RF"].dropna().mode().empty
        else "Sin categoría"
    )

    cambio_u = ((unidades_sim / unidades_base) - 1) * 100 if unidades_base else np.nan
    cambio_i = ((ingreso_sim / ingreso_base) - 1) * 100 if ingreso_base else np.nan
    cambio_m = ((margen_sim / margen_base) - 1) * 100 if margen_base else np.nan

    riesgos = []
    if pd.notna(elasticidad_prom) and elasticidad_prom >= 0:
        riesgos.append("elasticidad positiva")
    if "R2" in df_selected.columns and pd.notna(df_selected["R2"].mean()) and df_selected["R2"].mean() < 0.30:
        riesgos.append("R² bajo")
    if "P_Value" in df_selected.columns and pd.notna(df_selected["P_Value"].mean()) and df_selected["P_Value"].mean() > 0.10:
        riesgos.append("p-value alto")
    if "Observaciones" in df_selected.columns and df_selected["Observaciones"].sum() < 30:
        riesgos.append("pocas observaciones")
    if "Costo_Unitario_Base" in df_selected.columns and "Precio_Base" in df_selected.columns:
        if (df_selected["Costo_Unitario_Base"] >= df_selected["Precio_Base"]).any():
            riesgos.append("costo mayor o igual a precio")

    sujeto = f"el SKU {sku}" if sku else "el grupo filtrado"
    mejora_ingreso = "mejora" if pd.notna(cambio_i) and cambio_i > 0 else "no mejora"
    mejora_margen = "mejora" if pd.notna(cambio_m) and cambio_m > 0 else "no mejora"
    direccion_unidades = "suben" if pd.notna(cambio_u) and cambio_u > 0 else "bajan o se mantienen"

    riesgo_txt = " Riesgos: " + ", ".join(riesgos) + "." if riesgos else " No se observan riesgos críticos inmediatos."

    return (
        f"Para {sujeto}, el escenario '{escenario}' deja una categoría dominante '{categoria}' "
        f"con elasticidad promedio {format_num(elasticidad_prom, 3)}. "
        f"El ingreso {mejora_ingreso} ({format_pct(cambio_i)}), el margen {mejora_margen} ({format_pct(cambio_m)}) "
        f"y las unidades {direccion_unidades} ({format_pct(cambio_u)}). "
        f"Unidades simuladas: {format_num(unidades_sim, 0)}, ingreso simulado: {format_money(ingreso_sim)}, "
        f"margen simulado: {format_money(margen_sim)}.{riesgo_txt}"
    )
