"""Diagnóstico de calidad de datos."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (
    MIN_FILAS_ANALISIS,
    MIN_OBSERVACIONES,
    MIN_PRECIOS_DISTINTOS,
    MIN_SKUS_ANALISIS,
    UMBRAL_CV_VAR_ALTA,
    UMBRAL_REGISTROS_REMOVIDOS_AMARILLO,
    UMBRAL_REGISTROS_REMOVIDOS_ROJO,
)


def _coeficiente_variacion(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    media = s.mean()
    if len(s) == 0 or pd.isna(media) or media == 0:
        return np.nan
    return float(s.std() / abs(media))


def _safe_nunique(df: pd.DataFrame, column: str) -> int:
    return int(df[column].nunique(dropna=True)) if column in df.columns else 0


def _available_periods(df: pd.DataFrame, column: str) -> str:
    if column not in df.columns:
        return ""
    values = sorted(df[column].dropna().astype(str).unique().tolist())
    return ", ".join(values)


def _sku_variance_table(ventas: pd.DataFrame) -> pd.DataFrame:
    if not {"prod_nbr", "precio_unitario", "qty"}.issubset(ventas.columns):
        return pd.DataFrame(columns=["SKU", "varianza_precio", "varianza_unidades", "observaciones", "datos_suficientes"])
    out = (
        ventas.groupby("prod_nbr", as_index=False)
        .agg(
            varianza_precio=("precio_unitario", "var"),
            varianza_unidades=("qty", "var"),
            observaciones=("prod_nbr", "size"),
            precios_distintos=("precio_unitario", "nunique"),
        )
        .rename(columns={"prod_nbr": "SKU"})
    )
    out["datos_suficientes"] = (out["observaciones"] >= MIN_OBSERVACIONES) & (out["precios_distintos"] >= MIN_PRECIOS_DISTINTOS)
    return out


def build_quality_diagnostics(
    ventas_limpias: pd.DataFrame,
    resumen_limpieza: pd.DataFrame,
    summary: dict,
    semaforo_datos: pd.DataFrame,
    calidad_varianza: pd.DataFrame,
) -> pd.DataFrame:
    """Consolida la tabla interna diagnostico_calidad con métricas claras de Fase 1."""
    ventas = ventas_limpias.copy()
    row = semaforo_datos.iloc[0].to_dict() if semaforo_datos is not None and not semaforo_datos.empty else {}
    sku_var = _sku_variance_table(ventas)
    suficientes = int(sku_var["datos_suficientes"].sum()) if not sku_var.empty else 0
    insuficientes = int((~sku_var["datos_suficientes"]).sum()) if not sku_var.empty else 0

    registros = [
        ("registros_iniciales", summary.get("filas_originales", row.get("Filas_Originales", 0)), "Filas antes de limpieza"),
        ("registros_finales", len(ventas), "Filas en ventas_limpias"),
        ("registros_eliminados", summary.get("registros_removidos", row.get("Registros_Removidos", 0)), "Filas removidas por reglas de calidad"),
        ("porcentaje_eliminado", summary.get("porcentaje_removido", 0) * 100, "Porcentaje de registros removidos"),
        ("duplicados_eliminados", summary.get("duplicados_eliminados", summary.get("duplicados_originales", 0)), "Duplicados removidos"),
        ("SKUs_unicos", _safe_nunique(ventas, "prod_nbr"), "SKUs únicos finales"),
        ("tiendas_unicas", _safe_nunique(ventas, "store_nm"), "Tiendas únicas finales"),
        ("categorias_unicas", _safe_nunique(ventas, "subdept_nm"), "Categorías únicas finales"),
        ("departamentos_unicos", _safe_nunique(ventas, "dept_nm"), "Departamentos únicos finales"),
        ("meses_disponibles", _available_periods(ventas, "periodo_mensual"), "Periodos mensuales disponibles"),
        ("trimestres_disponibles", _available_periods(ventas, "periodo_trimestral"), "Periodos trimestrales disponibles"),
        ("semestres_disponibles", _available_periods(ventas, "periodo_semestral"), "Periodos semestrales disponibles"),
        ("años_disponibles", _available_periods(ventas, "periodo_anual"), "Años disponibles"),
        ("varianza_precio_por_SKU_promedio", float(sku_var["varianza_precio"].mean()) if not sku_var.empty else np.nan, "Promedio de varianza de precio por SKU"),
        ("varianza_unidades_por_SKU_promedio", float(sku_var["varianza_unidades"].mean()) if not sku_var.empty else np.nan, "Promedio de varianza de unidades por SKU"),
        ("SKUs_con_datos_suficientes", suficientes, f">= {MIN_OBSERVACIONES} observaciones y >= {MIN_PRECIOS_DISTINTOS} precios"),
        ("SKUs_con_datos_insuficientes", insuficientes, "No cumplen mínimos para análisis robusto"),
        ("semaforo_general_calidad", row.get("Semaforo", "🔴 Rojo"), row.get("Interpretacion", "Sin diagnóstico")),
        ("motivos_semaforo", row.get("Motivos", ""), "Alertas principales"),
    ]

    for col, nulos in summary.get("nulos_por_columna_final", {}).items():
        registros.append((f"nulos_final_{col}", int(nulos), "Nulos por columna en ventas_limpias"))

    if not calidad_varianza.empty:
        for _, var_row in calidad_varianza.iterrows():
            registros.append((
                f"coeficiente_variacion_{var_row.get('Columna')}",
                var_row.get("Coeficiente_Variacion", np.nan),
                f"Variable: {var_row.get('Variable', '')}; varianza alta: {bool(var_row.get('Varianza_Alta', False))}",
            ))

    diagnostico = pd.DataFrame(registros, columns=["metrica", "valor", "detalle"])
    return diagnostico


def calculate_quality_diagnosis(
    ventas_limpias: pd.DataFrame,
    resumen_limpieza: pd.DataFrame,
    summary: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calcula semáforo de calidad siguiendo la lógica del notebook base."""
    ventas = ventas_limpias.copy()

    variables_calidad = {
        "qty": "cantidad de unidades",
        "net_sale": "venta neta",
        "precio_unitario": "precio unitario",
        "costo_unitario": "costo unitario",
        "margen_unitario": "margen unitario",
        "margen_total": "margen total",
    }

    metricas_varianza = []
    for col, nombre in variables_calidad.items():
        cv = _coeficiente_variacion(ventas[col]) if col in ventas.columns else np.nan
        metricas_varianza.append(
            {
                "Variable": nombre,
                "Columna": col,
                "Coeficiente_Variacion": cv,
                "Varianza_Alta": bool(pd.notna(cv) and cv >= UMBRAL_CV_VAR_ALTA),
            }
        )

    calidad_varianza = pd.DataFrame(metricas_varianza)

    variables_varianza_alta = calidad_varianza.loc[
        calidad_varianza["Varianza_Alta"], "Variable"
    ].tolist()

    filas_originales = int(summary.get("filas_originales", 0))
    registros_removidos = int(summary.get("registros_removidos", filas_originales - len(ventas)))
    porcentaje_removido = float(summary.get("porcentaje_removido", 1 if filas_originales == 0 else registros_removidos / filas_originales))

    skus_unicos = ventas["prod_nbr"].nunique() if "prod_nbr" in ventas.columns else 0
    skus_con_obs_suficientes = int((ventas.groupby("prod_nbr").size() >= MIN_OBSERVACIONES).sum()) if "prod_nbr" in ventas.columns else 0
    skus_con_precios_suficientes = (
        int((ventas.groupby("prod_nbr")["precio_unitario"].nunique() >= MIN_PRECIOS_DISTINTOS).sum())
        if {"prod_nbr", "precio_unitario"}.issubset(ventas.columns)
        else 0
    )

    motivos = []

    if len(ventas) < MIN_FILAS_ANALISIS:
        motivos.append("datos insuficientes por pocas filas limpias")

    if skus_unicos < MIN_SKUS_ANALISIS:
        motivos.append("datos insuficientes por pocos SKUs")

    if skus_con_obs_suficientes == 0 or skus_con_precios_suficientes == 0:
        motivos.append("ningún SKU cumple mínimos de observaciones o variación de precio")

    if porcentaje_removido >= UMBRAL_REGISTROS_REMOVIDOS_ROJO:
        motivos.append("se removió más del 50% de los registros")

    if len(motivos) > 0:
        semaforo = "🔴 Rojo"
        interpretacion = "Base no confiable para recomendaciones automáticas."
    elif len(variables_varianza_alta) > 0 or porcentaje_removido >= UMBRAL_REGISTROS_REMOVIDOS_AMARILLO:
        semaforo = "🟡 Amarillo"
        interpretacion = "Base usable con restricciones."
        if variables_varianza_alta:
            motivos.append("varianza alta en " + ", ".join(variables_varianza_alta))
        if porcentaje_removido >= UMBRAL_REGISTROS_REMOVIDOS_AMARILLO:
            motivos.append("se removió una proporción relevante de registros en limpieza")
    else:
        semaforo = "🟢 Verde"
        interpretacion = "Base apta para pricing dinámico."
        motivos.append("sin alertas críticas")

    semaforo_datos = pd.DataFrame(
        [
            {
                "Semaforo": semaforo,
                "Interpretacion": interpretacion,
                "Filas_Originales": filas_originales,
                "Filas_Limpias": int(len(ventas)),
                "Registros_Removidos": registros_removidos,
                "%_Registros_Removidos": porcentaje_removido * 100,
                "Porcentaje_Datos_Faltantes_Original": summary.get("faltantes_pct_original", np.nan),
                "Duplicados_Originales": summary.get("duplicados_originales", np.nan),
                "Duplicados_Eliminados": summary.get("duplicados_eliminados", np.nan),
                "Valores_Infinitos_Detectados": summary.get("infinitos_detectados_original", np.nan),
                "Registros_Precio_Invalido": summary.get("registros_precio_invalido", np.nan),
                "Registros_Cantidad_Invalida": summary.get("registros_cantidad_invalida", np.nan),
                "Registros_Costo_Mayor_O_Igual_Precio": summary.get("registros_costo_mayor_o_igual_precio", np.nan),
                "SKUs_Unicos": skus_unicos,
                "Tiendas_Unicas": ventas["store_nm"].nunique() if "store_nm" in ventas.columns else 0,
                "Categorias_Unicas": ventas["subdept_nm"].nunique() if "subdept_nm" in ventas.columns else 0,
                "Departamentos_Unicos": ventas["dept_nm"].nunique() if "dept_nm" in ventas.columns else 0,
                "Meses_Disponibles": _available_periods(ventas, "periodo_mensual"),
                "Trimestres_Disponibles": _available_periods(ventas, "periodo_trimestral"),
                "Semestres_Disponibles": _available_periods(ventas, "periodo_semestral"),
                "Años_Disponibles": _available_periods(ventas, "periodo_anual"),
                "SKUs_Con_Obs_Suficientes": skus_con_obs_suficientes,
                "SKUs_Con_Precios_Suficientes": skus_con_precios_suficientes,
                "Motivos": "; ".join(motivos),
            }
        ]
    )

    return semaforo_datos, calidad_varianza
