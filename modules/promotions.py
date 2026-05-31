"""Utilidades compartidas para escenarios promocionales de pricing."""

from __future__ import annotations

import numpy as np
import pandas as pd

DEMANDA_BASE_BAJA_MINIMA = 5

PROMOCIONES_PRICING = pd.DataFrame(
    [
        {
            "escenario_id": "promocion_2x1",
            "nombre_escenario": "promoción 2x1",
            "tipo_escenario": "promocion_2x1",
            "factor_precio": 0.50,
            "descuento_efectivo": 0.50,
            "cambio_precio_pct": -0.50,
        },
        {
            "escenario_id": "promocion_3x2",
            "nombre_escenario": "promoción 3x2",
            "tipo_escenario": "promocion_3x2",
            "factor_precio": 2 / 3,
            "descuento_efectivo": 0.3333,
            "cambio_precio_pct": -0.3333,
        },
        {
            "escenario_id": "promocion_segundo_50",
            "nombre_escenario": "promoción segundo producto al 50%",
            "tipo_escenario": "promocion_segundo_50",
            "factor_precio": 0.75,
            "descuento_efectivo": 0.25,
            "cambio_precio_pct": -0.25,
        },
    ]
)

PROMOTION_TYPES = set(PROMOCIONES_PRICING["tipo_escenario"])


def escenarios_con_promociones(escenarios_base: pd.DataFrame) -> pd.DataFrame:
    """Agrega promociones retail estándar a una tabla de escenarios simples."""
    base = escenarios_base.copy()
    if "factor_precio" not in base.columns:
        base["factor_precio"] = 1 + pd.to_numeric(base["cambio_precio_pct"], errors="coerce")
    if "descuento_efectivo" not in base.columns:
        base["descuento_efectivo"] = np.nan
    return pd.concat([base, PROMOCIONES_PRICING.copy()], ignore_index=True, sort=False)


def es_promocion(tipo_escenario) -> pd.Series | bool:
    """Indica si el tipo de escenario corresponde a una promoción."""
    if isinstance(tipo_escenario, pd.Series):
        return tipo_escenario.isin(PROMOTION_TYPES)
    return tipo_escenario in PROMOTION_TYPES


def evaluar_riesgo_promocion(
    tipo_escenario,
    elasticidad,
    demanda_base,
    costo_unitario,
    precio_efectivo,
    margen_simulado,
    confianza_demanda=None,
    confianza_elasticidad=None,
) -> pd.Series:
    """Devuelve Bajo/Medio/Alto para promociones según guardrails de negocio."""
    idx = getattr(tipo_escenario, "index", None)
    riesgo = pd.Series("Bajo", index=idx) if idx is not None else "Bajo"
    promo = es_promocion(tipo_escenario)

    def _serie(value, index):
        if isinstance(value, pd.Series):
            return value.reindex(index)
        return pd.Series(value, index=index)

    if idx is None:
        if not promo:
            return riesgo
        elasticidad_ok = pd.notna(elasticidad) and np.isfinite(elasticidad) and elasticidad < 0
        costo_ok = pd.isna(costo_unitario) or (pd.notna(precio_efectivo) and costo_unitario < precio_efectivo)
        demanda_ok = pd.notna(demanda_base) and demanda_base >= DEMANDA_BASE_BAJA_MINIMA
        margen_ok = pd.isna(margen_simulado) or margen_simulado >= 0
        baja_conf = str(confianza_demanda).strip().lower() in {"baja", "no usable", "no recomendable"} or str(confianza_elasticidad).strip().lower() in {"baja", "no usable", "no recomendable"}
        if not elasticidad_ok or not costo_ok or not demanda_ok or not margen_ok:
            return "Alto"
        return "Alto" if baja_conf else "Bajo"

    elasticidad_s = pd.to_numeric(_serie(elasticidad, idx), errors="coerce")
    demanda_s = pd.to_numeric(_serie(demanda_base, idx), errors="coerce")
    costo_s = pd.to_numeric(_serie(costo_unitario, idx), errors="coerce")
    precio_s = pd.to_numeric(_serie(precio_efectivo, idx), errors="coerce")
    margen_s = pd.to_numeric(_serie(margen_simulado, idx), errors="coerce")
    conf_dem = _serie(confianza_demanda, idx).astype(str).str.strip().str.lower()
    conf_ela = _serie(confianza_elasticidad, idx).astype(str).str.strip().str.lower()

    high = promo & (
        elasticidad_s.isna()
        | ~np.isfinite(elasticidad_s)
        | elasticidad_s.ge(0)
        | demanda_s.lt(DEMANDA_BASE_BAJA_MINIMA)
        | demanda_s.isna()
        | precio_s.isna()
        | (costo_s.notna() & costo_s.ge(precio_s))
        | margen_s.lt(0)
    )
    low_conf = promo & (conf_dem.isin({"baja", "no usable", "no recomendable"}) | conf_ela.isin({"baja", "no usable", "no recomendable"}))
    riesgo.loc[high | low_conf] = "Alto"
    return riesgo


def razon_promocion_no_margen(costo_unitario) -> pd.Series | bool:
    """Detecta ausencia de costo para explicar que se optimiza por ingreso."""
    if isinstance(costo_unitario, pd.Series):
        return pd.to_numeric(costo_unitario, errors="coerce").isna()
    return pd.isna(costo_unitario)
