import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.historical_pricing import (
    PRICING_HISTORICO_ESCENARIOS_COLUMNS,
    build_pricing_historico_escenarios,
)


def test_build_pricing_historico_escenarios_uses_real_period_and_existing_elasticity():
    ventas = pd.DataFrame(
        [
            {
                "tran_date": "2024-01-05",
                "prod_nbr": "SKU1",
                "qty": 10,
                "net_sale": 100,
                "costo2": 6,
                "dept_nm": "Papelería",
                "subdept_nm": "Cuadernos",
            },
            {
                "tran_date": "2024-01-20",
                "prod_nbr": "SKU1",
                "qty": 10,
                "net_sale": 100,
                "costo2": 6,
                "dept_nm": "Papelería",
                "subdept_nm": "Cuadernos",
            },
        ]
    )
    elasticidades = pd.DataFrame(
        [
            {
                "SKU": "SKU1",
                "categoria": "Cuadernos",
                "departamento": "Papelería",
                "periodo_tipo": "mensual",
                "periodo": "2024-01",
                "fecha_inicio": "2024-01-01",
                "fecha_fin": "2024-01-31",
                "elasticidad": -1.0,
                "r2": 0.8,
                "p_value": 0.02,
                "num_observaciones": 10,
                "num_precios_distintos": 3,
                "precio_promedio": 10,
                "unidades_promedio": 20,
                "ingreso_promedio": 200,
                "margen_promedio": 80,
                "confianza_elasticidad": "Alta",
                "recomendable_elasticidad": True,
                "razon_no_recomendable": "",
            }
        ]
    )

    out = build_pricing_historico_escenarios(ventas, elasticidades, periodo_tipos=["mensual"])

    assert list(out.columns) == PRICING_HISTORICO_ESCENARIOS_COLUMNS
    assert len(out) == 9
    assert set(out["nombre_escenario"]) == {
        "bajar precio 20%",
        "bajar precio 15%",
        "bajar precio 10%",
        "bajar precio 5%",
        "mantener precio",
        "subir precio 5%",
        "subir precio 10%",
        "subir precio 15%",
        "subir precio 20%",
    }
    keep = out.loc[out["nombre_escenario"].eq("mantener precio")].iloc[0]
    assert keep["precio_real"] == 10
    assert keep["precio_efectivo"] == 10
    assert keep["unidades_reales"] == 20
    assert keep["unidades_simuladas"] == 20
    assert keep["ingreso_real"] == 200
    assert keep["margen_real"] == 80
    assert keep["tipo_elasticidad_usada"] == "elasticidad_sku_periodo"
